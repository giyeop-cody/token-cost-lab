#!/usr/bin/env python3
"""A/B ladder execution budgets. No hypothetical prevented turn is a live effect."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'agent_setup'))
from router import Tier,cost_of,FIRST_OUT_TOK,REWORK_OUT_TOK
from ladder_b import rung_cost

print('[증거 범위] 고정 토큰·티어 예산의 시나리오. live 정책 A/B 아님.')
p=json.loads((ROOT/'demo/results.json').read_text())
print(f"과거 페르소나: ${p['A']['cost']:.7f} / ${p['B']['cost']:.7f}, {p['ratio']}배 (Sonnet 가격, 전체 시나리오)")
print('아래는 별도 티어 가격의 실행 한 칸 예산이다. 전체 세션과 나누어 절감률을 만들지 않는다.')
patch=cost_of(Tier.MID,1800,REWORK_OUT_TOK)
full=cost_of(Tier.MID,1800,FIRST_OUT_TOK)
print(f'동일 MID/unit 입력1800: 2500출력 ${full:.5f}, 900출력 ${patch:.5f} ({full/patch:.2f}배 비용비)')
for tier,scope in ((Tier.MID,'file'),(Tier.LARGE,'file'),(Tier.LARGE,'module')):
    print(f'가정한 B 실행: {tier.name}/{scope} ${rung_cost(tier,1800,scope=scope,reset=False):.5f}')
print('짧은 패치가 성공하고 AC가 해당 결함을 검출한다는 조건이 있어야 운영 절감이 된다.')
print('과거 턴4·5를 실제 예방했거나 턴6이 소멸했다고 관측하지 않았다. 사람 시간·재시도도 별도다.')
