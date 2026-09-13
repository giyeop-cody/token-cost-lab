# -*- coding: utf-8 -*-
"""A/B 각각 따로 쓸 때의 효용 — 실로그 기준 비용 비교."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"agent_setup"))
from router import Tier, cost_of, rework_cost, FIRST_OUT_TOK, REWORK_OUT_TOK
from ladder_b import rung_cost

TI = 1800

print("="*80)
print("실로그 기준 — 반려 5턴을 어떤 장치로 막느냐에 따른 비용")
print("="*80)

# 실측 기준선 (demo/results.json)
A_REAL, B_REAL = 1.0361, 0.0498
print(f"\n[0] 실측 기준선")
print(f"    장치 없음(페르소나 A 6턴) = ${A_REAL:.4f}")
print(f"    스펙 선주입(페르소나 B 2턴) = ${B_REAL:.4f}   → {A_REAL/B_REAL:.1f}배")

# 관할 분해 (ab_efficacy.py 결과)
#   턴4,5 = AC로 잡히는 기능 결함  → A 사다리 관할
#   턴2   = 스펙 미합의            → B 관할 (사용자가 봐야 안다)
#   턴3   = 취향                   → 어느 쪽도 못 고침
#   턴6   = 턴2~5의 파생           → 앞을 막으면 소멸
print(f"\n[1] A 사다리만 켰을 때 (트리거=AC 실패)")
print(f"    잡는 턴: 4,5  — 결정론 AC로 검출 가능")
a_rung = [
    ("retry  mid/unit", cost_of(Tier.MID, TI, REWORK_OUT_TOK)),
]
a_cost = a_rung[0][1]
print(f"    턴4를 A 1칸(retry)으로 처리 = ${a_cost:.4f}")
print(f"    턴5도 동일               = ${a_cost:.4f}")
print(f"    합계 ${a_cost*2:.4f}  ← 사용자에게 안 나가고 턴 안에서 끝난다")

print(f"\n[2] B 사다리만 켰을 때 (트리거=사용자 반려)")
b1 = rung_cost(Tier.MID, TI, reset=False, scope="file")
b2 = rung_cost(Tier.LARGE, TI, reset=False, scope="file")
b3 = rung_cost(Tier.LARGE, TI, reset=False, scope="module")
print(f"    수정된 트리거로 실로그 재생 → 4칸 발화(턴2,4,5,6)")
print(f"      턴2 widen   mid/file   = ${b1:.4f}")
print(f"      턴4 widen   mid/file   = ${b1:.4f}")
print(f"      턴5 tier-up large/file = ${b2:.4f}")
print(f"      턴6 widen-2 large/module=${b3:.4f}")
tot_b = b1*2 + b2 + b3
print(f"    합계 ${tot_b:.4f}")

print(f"\n[3] 문제 — B가 턴4·5(기능 결함)까지 처리하면")
print(f"    같은 두 턴을 A로 처리: ${a_cost*2:.4f}")
print(f"    B로 처리:             ${b1+b2:.4f}")
print(f"    B가 {(b1+b2)/(a_cost*2):.1f}배 비싸다 — 게다가 턴5는 티어를 LARGE로 올렸는데")
print(f"    실제 원인은 '리스너 재등록 누락'이라 모델 능력 문제가 아니다.")

print(f"\n[4] A+B 결합 (A가 먼저, 못 잡은 것만 B로)")
print(f"    턴4,5 → A가 AC로 선제 차단  = ${a_cost*2:.4f}")
print(f"    턴2   → B 1칸(스펙 미합의)  = ${b1:.4f}")
print(f"    턴3   → 취향, 예시 제시(same칸) = ${cost_of(Tier.MID, TI, REWORK_OUT_TOK):.4f}")
print(f"    턴6   → 발생 안 함 (파생)   = $0")
combined = a_cost*2 + b1 + cost_of(Tier.MID, TI, REWORK_OUT_TOK)
print(f"    합계 ${combined:.4f}")

print("\n" + "="*80)
print("정리")
print("="*80)
print(f"  장치 없음      ${A_REAL:.4f}   (실측)")
print(f"  B 단독         ${tot_b:.4f}   ({A_REAL/tot_b:.1f}배 절감, 그러나 기능결함까지 B가 처리)")
print(f"  A+B 결합       ${combined:.4f}   ({A_REAL/combined:.1f}배 절감)")
print(f"  스펙 선주입    ${B_REAL:.4f}   (실측 — 애초에 반려를 안 만든다)")
