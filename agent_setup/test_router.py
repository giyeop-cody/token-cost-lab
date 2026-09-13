# -*- coding: utf-8 -*-
"""router.py 검증 — 라이브 시연용. 의존성 없음: python3 test_router.py"""
from router import (Kind, Tier, SessionMemory, classify, route,
                    explain_guard, estimate, cost_of,
                    escalate, ReworkTracker, rework_cost, breakeven,
                    looks_rejected,
                    SCOPE_LADDER)

P = F = 0


def check(name, cond, extra=""):
    global P, F
    if cond:
        P += 1
        print(f"  PASS  {name}")
    else:
        F += 1
        print(f"  FAIL  {name}  {extra}")


print("\n[1] 분류 정확도")
CASES = [
    ("결제 모듈 아키텍처 설계 트레이드오프 정리해줘", Kind.REASONING),
    ("어떤 방식이 나은지 비교해서 결정해줘", Kind.REASONING),
    ("스펙대로 핸들러 구현해줘", Kind.IMPLEMENT),
    ("이 버그 고쳐줘", Kind.IMPLEMENT),
    ("방금 짠 코드 설명해줘", Kind.EXPLAIN),
    ("이게 무슨 뜻이야", Kind.EXPLAIN),
    ("src 밑에서 TODO 전부 grep 해줘", Kind.TOOL),
    ("이 파일 이름 바꿔줘", Kind.TOOL),
    ("경쟁사 40개 가격 페이지 조사해서 정규화해줘", Kind.BULK),
    ("이 데이터 일괄 라벨링해줘", Kind.BULK),
]
for task, want in CASES:
    got, by = classify(task)
    check(f"{task[:28]:<30s} → {got.value}", got is want, f"(기대 {want.value})")

print("\n[2] 라우팅 티어")
check("추론 → 웹 세션", route(CASES[0][0]).tier is Tier.EXTERNAL)
check("추론 + 웹금지 → LARGE",
      route(CASES[0][0], allow_external=False).tier is Tier.LARGE)
check("구현 → MID", route("스펙대로 핸들러 구현해줘").tier is Tier.MID)
check("툴 → SMALL", route("이 파일 이름 바꿔줘").tier is Tier.SMALL)
check("대량 → BATCH", route(CASES[8][0]).tier is Tier.BATCH)
check("대량 + 마감 → MID(동기)",
      route(CASES[8][0], deadline_sensitive=True).tier is Tier.MID)

print("\n[3] 설명 3줄 강제")
d = route("방금 짠 코드 설명해줘")
check("암묵적 설명 → 3-lines", d.options.get("explain") == "3-lines")
d2 = route("이 알고리즘 왜 그런지 끝까지 자세히 설명해줘")
check("명시적 상세요청 → full", d2.options.get("explain") == "full")
long_txt = "\n".join(f"{i}번째 줄 설명입니다." for i in range(1, 13))
out = explain_guard(long_txt)
check("12줄 → 4줄(3 + 생략고지)", len(out.splitlines()) == 4,
      f"실제 {len(out.splitlines())}")
check("생략 고지 포함", "생략" in out)
check("짧은 입력은 그대로", explain_guard("한 줄.") == "한 줄.")

print("\n[4] 세션 위생 — 반복은 컴팩션, 어긋남만 리셋")
m = SessionMemory(repeat_threshold=3)
r1 = m.observe("이 함수는 사용자 입력을 검증합니다.", 120)
r2 = m.observe("전혀 다른 새로운 설명입니다.", 130)
r3 = m.observe("이 함수는  사용자 입력을 검증합니다!!", 120)  # 표기만 다름
check("1회차 continue", r1["action"] == "continue")
check("타 내용은 continue", r2["action"] == "continue")
check("2회 반복만으로는 리셋하지 않음", r3["action"] == "continue", r3)
check("정규화가 공백·문장부호 무시", r3["repeat"] == 2)

r4 = m.observe("이 함수는 사용자 입력을 검증합니다.", 120)
check("3회 반복 → 컴팩션(리셋 아님)", r4["action"] == "compact", r4)
check("컴팩션은 세션을 버리지 않음", "carry_over" not in r4)
check("컴팩션은 남길 것을 지정", "keep" in r4 and "drop" in r4)
check("진행 중에는 리셋이 나오지 않음", m.resets == 0, m.resets)
check("누적 토큰 집계", m.tokens_in_context == 490, m.tokens_in_context)

mb = SessionMemory(bloat_tokens=1000)
check("컨텍스트 비대 → 컴팩션",
      mb.observe("짧은 답", 1200)["action"] == "compact")

# 완료 시점 판정 — 리셋은 여기서만
mr = SessionMemory()
check("완료 전에는 판정하지 않음",
      mr.review(done=False)["action"] == "continue")
check("검증 실패는 리셋이 아니라 리워크",
      mr.review(done=True, ac_passed=False)["action"] == "rework")
check("리워크 판정은 세션을 버리지 않음", mr.resets == 0, mr.resets)

rv = mr.review(done=True, ac_passed=True, user_verdict="이게 아니라 반대 방향인데요")
check("완료했으나 방향이 어긋남 → reset", rv["action"] == "reset", rv)
check("어긋남 신호 표기", rv["signal"] == "misaligned")
check("리셋 시 이월 지침 제공", "carry_over" in rv)
check("리셋 카운트 증가", mr.resets == 1, mr.resets)

check("통과하면 continue",
      mr.review(done=True, ac_passed=True)["action"] == "continue")

check("거부 표현 감지", looks_rejected("그게 아니고요"))
check("정상 표현은 통과 아님", not looks_rejected("좋습니다. 다음 단계로 가죠"))

print("\n[5] 비용 산식")
check("SMALL 1M/1M = $0.75", abs(cost_of(Tier.SMALL, 10**6, 10**6) - 0.75) < 1e-9)
check("BATCH는 MID의 50%",
      abs(cost_of(Tier.BATCH, 10**6, 10**6) * 2
          - cost_of(Tier.MID, 10**6, 10**6)) < 1e-9)
check("웹 세션은 종량 0원", cost_of(Tier.EXTERNAL, 10**6, 10**6) == 0.0)

e = estimate([t[:1] + (1000, 2000) for t in CASES])
check("절감률 0~100% 범위", 0 < e["saved_pct"] < 100, e["saved_pct"])
check("라우팅이 기준선보다 저렴", e["routed_usd"] < e["baseline_usd"])
print(f"        기준선 ${e['baseline_usd']:.4f} → 라우팅 ${e['routed_usd']:.4f}"
      f"  ({e['saved_pct']:.1f}% 절감)")


print("\n[6] 리워크 사다리 — 한 칸에 축 하나씩")
d1 = route("정해진 스펙대로 결제 핸들러 구현해줘")
check("첫 배정은 attempt=1 · scope=unit", d1.attempt == 1 and d1.scope == "unit",
      f"{d1.attempt}/{d1.scope}")
check("첫 배정은 리셋 없음", d1.reset is False)

d2 = escalate(d1)
check("2회차는 제자리 재시도", d2.step == "retry", d2.step)
check("2회차 티어 그대로", d2.tier is d1.tier, d2.tier)
check("2회차 범위 그대로", d2.scope == "unit", d2.scope)
check("2회차는 리셋하지 않음 — 맥락을 지킨다", d2.reset is False, d2.reset)
check("리워크 턴은 출력 상한을 건다", d2.options.get("max_out_tok") == 900,
      d2.options.get("max_out_tok"))
check("리워크 턴은 전문 재작성이 아니라 패치",
      d2.options.get("output") == "unified-diff", d2.options.get("output"))
check("실패 근거 첨부 지시", "attach" in d2.options)
check("진단 우선 지시", d2.options.get("explain") == "diagnosis-first")

d3 = escalate(d2)
check("3회차는 범위 확대", d3.step == "widen", d3.step)
check("3회차 범위 unit→file", d3.scope == "file", d3.scope)
check("3회차 티어는 아직 올리지 않음", d3.tier is d1.tier, d3.tier)
check("3회차부터 리셋", d3.reset is True)
check("리셋 시 이월 지침", d3.carry_over and "specs" in d3.carry_over)

d4 = escalate(d3)
check("4회차에 비로소 티어 상승", d4.step == "tier-up", d4.step)
check("4회차 mid→large", d4.tier is Tier.LARGE, d4.tier)
check("4회차 범위는 유지", d4.scope == "file", d4.scope)
check("4회차는 테스트 우선 강제",
      d4.options.get("require") == "write-test-first")
check("상위 티어에서는 진단만 짧게 받는다",
      d4.options.get("max_out_tok") == 400, d4.options.get("max_out_tok"))
check("상위 티어 진단 → 적용은 한 단계 아래가",
      d4.options.get("apply_with") == "mid", d4.options.get("apply_with"))

d5 = escalate(d4)
check("5회차는 구현 중단 → respec", d5.scope == "respec", d5.scope)
check("5회차는 설계 종류로 전환", d5.kind is Kind.REASONING, d5.kind)
check("5회차는 LARGE로 더 올리지 않음", d5.tier is not Tier.LARGE, d5.tier)
check("스펙 산출물을 요구", d5.options.get("output") == "spec.md")

d6 = escalate(d5, attempt=9)
check("사다리 밖으로 나가지 않음", d6.scope in SCOPE_LADDER, d6.scope)

ds = route("방금 짠 코드 설명해줘")
check("SMALL 시작", ds.tier is Tier.SMALL, ds.tier)
check("SMALL도 2회차는 제자리", escalate(ds).tier is Tier.SMALL, escalate(ds).tier)
check("SMALL→MID는 4회차에",
      escalate(escalate(escalate(ds))).tier is Tier.MID)

print("\n[7] 리워크 추적")
t = ReworkTracker()
a = t.first("x", "정해진 스펙대로 결제 핸들러 구현해줘")
b = t.again("x", a)
c = t.again("x", b)
check("시도 횟수 누적", t.attempts["x"] == 3, t.attempts["x"])
check("재시도 턴 = 2", t.rework_turns() == 2, t.rework_turns())
check("이력 3건 기록", len(t.history) == 3, len(t.history))
check("이력에 단계 기록", [h["step"] for h in t.history] == ["first", "retry", "widen"],
      [h["step"] for h in t.history])
check("리셋 1회 집계", t.resets() == 1, t.resets())
check("리포트에 최다 리워크 표기", "x" in t.report(), t.report())
t.first("y", "src 밑에서 TODO 전부 grep 해줘")
check("무사고 작업은 리워크 0 기여", t.rework_turns() == 2, t.rework_turns())

print("\n[8] 리워크 비용 — 짧은 리워크에서 손해가 없어야 한다")
T, TI, TO = "정해진 스펙대로 결제 핸들러 구현해줘", 1800, 2500

a0 = rework_cost(T, TI, TO, fails=0, strategy="retry")
b0 = rework_cost(T, TI, TO, fails=0, strategy="escalate")
check("실패 0회: 첫 배정은 상한 없음(전문 작성)",
      abs(a0["usd"] - b0["usd"]) < 1e-9, f"{a0['usd']:.4f} vs {b0['usd']:.4f}")
check("첫 턴 출력은 깎지 않는다", b0["trail"][0]["out_tok"] == TO,
      b0["trail"][0]["out_tok"])

for f in (1, 2):
    a = rework_cost(T, TI, TO, fails=f, strategy="retry")
    b = rework_cost(T, TI, TO, fails=f, strategy="escalate")
    check(f"실패 {f}회: 사다리가 제자리보다 저렴(출력 상한 효과)",
          b["usd"] < a["usd"], f"{a['usd']:.4f} vs {b['usd']:.4f}")
    check(f"실패 {f}회: 리셋 {'0' if f == 1 else '1'}회",
          b["resets"] == (0 if f == 1 else 1), b["resets"])

rc_r = rework_cost(T, TI, TO, fails=3, strategy="retry")
rc_e = rework_cost(T, TI, TO, fails=3, strategy="escalate")
check("턴 수 일치", rc_r["turns"] == rc_e["turns"] == 4)
check("리워크 턴 출력이 상한선 이하",
      all(x["out_tok"] <= 900 for x in rc_e["trail"][1:]),
      [x["out_tok"] for x in rc_e["trail"]])
check("사다리 이력 = 재시도→범위→모델",
      [x["step"] for x in rc_e["trail"]] == ["first", "retry", "widen", "tier-up"],
      [x["step"] for x in rc_e["trail"]])
check("리셋 비용이 계상됨", rc_e["resets"] == 2, rc_e["resets"])

# 출력 상한은 사다리 전용이 아니다 — 정직하게 비교한다.
capped48 = sum(
    cost_of(Tier.MID, TI, TO if i == 0 else 900) for i in range(49))
lad48 = rework_cost(T, TI, TO, fails=48, strategy="escalate")["usd"]
check("상한을 제자리에도 적용하면 제자리도 크게 싸진다",
      capped48 < rework_cost(T, TI, TO, fails=48, strategy="retry")["usd"])
check("그래도 사다리가 더 싸다 — 진짜 기여는 상한선(5회차 중단)",
      lad48 < capped48, f"{lad48:.4f} vs {capped48:.4f}")

many_r = rework_cost(T, TI, TO, fails=10, strategy="retry")
many_e = rework_cost(T, TI, TO, fails=10, strategy="escalate")
check("길어지면 사다리가 역전", many_e["usd"] < many_r["usd"],
      f"{many_e['usd']:.4f} vs {many_r['usd']:.4f}")
cap = rework_cost(T, TI, TO, fails=48, strategy="escalate")
check("사다리는 상한이 있다", abs(cap["usd"] - many_e["usd"]) < 1e-9,
      f"{cap['usd']:.4f} vs {many_e['usd']:.4f}")

be = breakeven(T, TI, TO, esc_fails=2)
check("손익분기 턴이 산출됨", be["breakeven_retry_turns"] is not None)
check("손익분기가 에스컬레이션 턴 이하 — 사다리가 더 빨리 이긴다",
      be["breakeven_retry_turns"] <= be["escalate_turns"],
      f"{be['breakeven_retry_turns']} vs {be['escalate_turns']}\n"
      f"        사다리 3턴 ${be['escalate_usd']:.4f}  "
      f"=  제자리 {be['breakeven_retry_turns']}턴 ${be['breakeven_usd']:.4f}")

print("\n" + "=" * 60)
print(f"  {P + F}건 중 {P} PASS / {F} FAIL")
print("=" * 60)
raise SystemExit(1 if F else 0)
