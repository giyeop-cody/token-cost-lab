# -*- coding: utf-8 -*-
"""router.py 검증 — 라이브 시연용. 의존성 없음: python3 test_router.py"""
from router import (Kind, Tier, SessionMemory, classify, route,
                    explain_guard, estimate, cost_of,
                    escalate, ReworkTracker, rework_cost, breakeven,
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

print("\n[4] 세션 리셋 트리거")
m = SessionMemory(threshold=2)
r1 = m.observe("이 함수는 사용자 입력을 검증합니다.", 120)
r2 = m.observe("전혀 다른 새로운 설명입니다.", 130)
r3 = m.observe("이 함수는  사용자 입력을 검증합니다!!", 120)  # 표기만 다름
check("1회차 continue", r1["action"] == "continue")
check("타 내용은 continue", r2["action"] == "continue")
check("동일 설명 재등장 → reset", r3["action"] == "reset", r3)
check("정규화가 공백·문장부호 무시", r3["repeat"] == 2)
check("이월 지침 제공", "carry_over" in r3)
check("누적 토큰 집계", m.tokens_in_context == 370, m.tokens_in_context)

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


print("\n[6] 리워크 에스컬레이션")
d1 = route("정해진 스펙대로 결제 핸들러 구현해줘")
check("첫 배정은 attempt=1 · scope=unit", d1.attempt == 1 and d1.scope == "unit",
      f"{d1.attempt}/{d1.scope}")

d2 = escalate(d1)
check("2회차 티어 상승 mid→large", d2.tier is Tier.LARGE, d2.tier)
check("2회차 범위 확대 unit→file", d2.scope == "file", d2.scope)
check("실패 근거 첨부 지시", "attach" in d2.options)
check("2회차부터 3줄 상한 해제",
      d2.options.get("explain") == "diagnosis-first", d2.options.get("explain"))

d3 = escalate(d2)
check("3회차 범위 module", d3.scope == "module", d3.scope)
check("3회차는 테스트 우선 강제",
      d3.options.get("require") == "write-test-first")

d4 = escalate(d3)
check("4회차는 구현 중단 → respec", d4.scope == "respec", d4.scope)
check("4회차는 설계 종류로 전환", d4.kind is Kind.REASONING, d4.kind)
check("4회차는 LARGE로 더 올리지 않음", d4.tier is not Tier.LARGE, d4.tier)
check("스펙 산출물을 요구", d4.options.get("output") == "spec.md")

# 범위는 사다리를 벗어나지 않는다
d5 = escalate(d4, attempt=9)
check("사다리 밖으로 나가지 않음", d5.scope in SCOPE_LADDER, d5.scope)

# SMALL에서 시작해도 한 단계씩만 오른다
ds = route("방금 짠 코드 설명해줘")
check("SMALL 시작", ds.tier is Tier.SMALL, ds.tier)
check("SMALL→MID 한 단계만", escalate(ds).tier is Tier.MID, escalate(ds).tier)

print("\n[7] 리워크 추적")
t = ReworkTracker()
a = t.first("x", "정해진 스펙대로 결제 핸들러 구현해줘")
b = t.again("x", a)
c = t.again("x", b)
check("시도 횟수 누적", t.attempts["x"] == 3, t.attempts["x"])
check("재시도 턴 = 2", t.rework_turns() == 2, t.rework_turns())
check("이력 3건 기록", len(t.history) == 3, len(t.history))
check("리포트에 최다 리워크 표기", "x" in t.report(), t.report())
t.first("y", "src 밑에서 TODO 전부 grep 해줘")
check("무사고 작업은 리워크 0 기여", t.rework_turns() == 2, t.rework_turns())

print("\n[8] 리워크 비용")
rc_r = rework_cost("정해진 스펙대로 결제 핸들러 구현해줘", 1800, 2500,
                   fails=3, strategy="retry")
rc_e = rework_cost("정해진 스펙대로 결제 핸들러 구현해줘", 1800, 2500,
                   fails=3, strategy="escalate")
check("같은 턴 수면 제자리 재시도가 저렴", rc_r["usd"] < rc_e["usd"],
      f"{rc_r['usd']:.4f} vs {rc_e['usd']:.4f}")
check("턴 수 일치", rc_r["turns"] == rc_e["turns"] == 4)
check("에스컬레이션 이력에 범위 확대 기록",
      [x["scope"] for x in rc_e["trail"]][:3] == ["unit", "file", "module"],
      [x["scope"] for x in rc_e["trail"]])

be = breakeven("정해진 스펙대로 결제 핸들러 구현해줘", 1800, 2500, esc_fails=2)
check("손익분기 턴이 산출됨", be["breakeven_retry_turns"] is not None)
check("손익분기는 에스컬레이션 턴보다 큼",
      be["breakeven_retry_turns"] > be["escalate_turns"],
      f"{be['breakeven_retry_turns']} vs {be['escalate_turns']}")
print(f"        에스컬레이션 {be['escalate_turns']}턴 ${be['escalate_usd']:.4f}"
      f"  =  제자리 {be['breakeven_retry_turns']}턴 ${be['breakeven_usd']:.4f}")

print("\n" + "=" * 60)
print(f"  {P + F}건 중 {P} PASS / {F} FAIL")
print("=" * 60)
raise SystemExit(1 if F else 0)
