# -*- coding: utf-8 -*-
"""사다리를 폐기하는 게 나은가 — 폐기 시 '기본값'이 무엇이 되는지로 판단."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"agent_setup"))
from router import Tier, cost_of, rework_cost, REWORK_OUT_TOK, FIRST_OUT_TOK
TI = 1800

print("="*78)
print("0. 지난 비교의 결함 — 서로 다른 세션을 비교했다")
print("="*78)
print("""
  이전 표:  A+B 결합 $0.0624  vs  스펙 선주입 $0.0498  → "스펙이 이긴다"

  그런데 두 숫자는 **같은 세션이 아니다**.
    $0.0624 = 반려가 5턴 터진 세션을, 사다리로 처리한 비용
    $0.0498 = 반려가 거의 안 터진 세션의, 총 세션 비용
  사다리와 스펙은 **대체재가 아니라 직교한다.** 같은 축에 놓고 비교한 것이 오류.
""")

print("="*78)
print("1. 스펙을 잘 써도 리워크는 0이 되지 않는다 — 실로그 증거")
print("="*78)
print("""
  페르소나 B 턴2 (원문):
    "확인함. 640px 미디어쿼리에서 목록 폭 110px이 너무 좁다. 140px로."

  로그 말미는 "리워크 없음"이라 적어두었지만, 이건 **산출물을 보고 고쳐달라는
  수정 요청**이다. 성격상 리워크다. 스펙을 아무리 잘 써도 화면을 봐야 아는 것은
  남는다. 즉 '스펙 선주입'은 리워크를 **0으로 만드는 장치가 아니라 줄이는 장치**다.
  → 리워크가 남는 한, 그걸 처리할 규칙은 여전히 필요하다.
""")

print("="*78)
print("2. 그래서 진짜 질문 — 사다리를 폐기하면 '기본값'이 무엇이 되나")
print("="*78)
print("""
  폐기 = 규칙 없음. 규칙이 없을 때 사람과 에이전트가 실제로 하는 행동은
  '아무것도 안 함'이 아니라 **제자리 재시도 반복**이다.
  그게 정확히 페르소나 A가 한 것이고, 실측 $1.0361이다.
""")
n = 4
retry    = rework_cost("메모장 저장 버그 수정", TI, FIRST_OUT_TOK, n, strategy="retry")
esc      = rework_cost("메모장 저장 버그 수정", TI, FIRST_OUT_TOK, n, strategy="escalate")
topfirst = rework_cost("메모장 저장 버그 수정", TI, FIRST_OUT_TOK, n, strategy="topfirst")
print(f"  같은 실패 {n}회를 처리하는 세 전략 (router.rework_cost 호출)")
print(f"    제자리 재시도(=폐기 시 기본값)  ${retry['usd']:.4f}")
print(f"    사다리(escalate)                ${esc['usd']:.4f}")
print(f"    처음부터 최상위                 ${topfirst['usd']:.4f}")
print(f"\n  >>> 사다리는 제자리 반복 대비 {retry['usd']/esc['usd']:.1f}배 절감")
print(f"  >>> 폐기하면 이 {retry['usd']-esc['usd']:.4f}가 그대로 돌아온다")

print("\n" + "="*78)
print("3. 공정한 비교 — 같은 세션에서 사다리만 껐다 켰다")
print("="*78)
# 스펙 선주입 세션(페르소나 B)에서도 리워크 1회(턴2)는 발생했다.
# 그 1회를 어떻게 처리하느냐만 비교한다.
spec_base = 0.0498
one_retry_inplace = cost_of(Tier.MID, TI, FIRST_OUT_TOK)   # 전체 재출력
one_rung_ladder   = cost_of(Tier.MID, TI, REWORK_OUT_TOK)  # 변경 블록만
print(f"  스펙 선주입 세션에서 발생한 리워크 1회를:")
print(f"    사다리 없이 (전체 재출력)   ${one_retry_inplace:.4f}")
print(f"    사다리 1칸  (변경분만)      ${one_rung_ladder:.4f}")
print(f"    → 리워크 1회에서도 {one_retry_inplace/one_rung_ladder:.1f}배 차이")
print(f"\n  사용자 요구였던 '짧은 리워크(1~2턴)에서도 이득' 조건: "
      f"{'충족' if one_rung_ladder < one_retry_inplace else '미충족'}")

print("\n" + "="*78)
print("4. 폐기 후보를 나눠서 판단 — 사다리는 한 덩어리가 아니다")
print("="*78)
rows = [
 ("A 사다리 (AC 실패 트리거)", "유지", "$0.0112/칸. 결정론 트리거라 오탐 없음. "
  "제자리 반복 대비 12.1배. 폐기 이유 없음"),
 ("B 사다리 (사용자 반려 트리거)", "조건부 유지", "트리거 수정 후 4/5·오탐 0. "
  "단 관할을 스펙 미합의로 좁혀야. 기능결함까지 맡으면 5.2배 손해"),
 ("B의 tier-up 칸", "폐기 검토", "실로그 턴5에서 LARGE로 올렸으나 "
  "원인은 리스너 누락 — 모델 능력 무관. 티어 상승이 정답인 건 reasoning 1종뿐"),
 ("B의 respec 칸", "유지", "$0. 구현을 멈추는 칸이라 비용이 없고 상한을 막는다"),
 ("의도 불일치 5종 분류", "유지+보강", "실로그 40%. 버그신고형 6번째 종 추가 필요"),
]
w = max(len(r[0]) for r in rows)
for name, verdict, why in rows:
    print(f"\n  {name:<{w}}  [{verdict}]")
    print(f"  {'':<{w}}   {why}")
