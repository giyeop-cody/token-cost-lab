#!/usr/bin/env python3
"""Illustrative policy budgets, not a causal keep/kill decision from live A/B."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'agent_setup'))
from router import Tier, cost_of, rework_cost, FIRST_OUT_TOK, REWORK_OUT_TOK

print('[증거 범위] 비용 시나리오. 완료 작업당 비용·성공률·사람 시간 미측정.')
print('사다리 유지 주장은 조건부다: 짧은 패치와 적절한 리셋을 품질 게이트와 함께 시도한다.')
print('실패 횟수 입력=4; respec에서 일찍 중단하면 동일 성공 결과 비교가 아니다.')
for strategy in ('retry','escalate','topfirst'):
    r=rework_cost('메모장 저장 버그 수정',1800,FIRST_OUT_TOK,4,strategy=strategy)
    print(strategy, f"paid-call budgets={r['turns']}, usd={r['usd']:.5f}; no quality outcome measured")
full=cost_of(Tier.MID,1800,FIRST_OUT_TOK)
patch=cost_of(Tier.MID,1800,REWORK_OUT_TOK)
print(f'출력 2500→900 가정만 비교: ${full:.5f}→${patch:.5f} ({full/patch:.2f}배)')
print('패치가 실제 적용되고 AC를 통과해야 운영 절감이다. 테스트 자체의 누락·오류 가능성도 있다.')
print('고정 발화의 비-unknown 비율은 정답 라벨 정확도가 아니다: analysis/replay_logs.py 참고.')
print('5종 중 reasoning 1종이라는 분류 구조가 실제 발생 빈도 20%를 뜻하지 않는다.')
print('respec은 추가 토큰 비용 0으로 모델링하지만 사람 시간과 미해결 비용은 제외다.')
