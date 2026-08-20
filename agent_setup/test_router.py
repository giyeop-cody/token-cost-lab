# -*- coding: utf-8 -*-
"""router.py 검증 — 라이브 시연용. 의존성 없음: python3 test_router.py"""
from router import (Kind, Tier, SessionMemory, classify, route,
                    explain_guard, estimate, cost_of)

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

print("\n" + "=" * 60)
print(f"  {P + F}건 중 {P} PASS / {F} FAIL")
print("=" * 60)
raise SystemExit(1 if F else 0)
