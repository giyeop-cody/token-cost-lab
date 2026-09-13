# -*- coding: utf-8 -*-
"""turn_growth_tok을 실측에서 역산한다. 임의값 금지."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"agent_setup"))
from router import rework_cost, cost_of, Tier

R = json.load(open(ROOT/"demo/results.json"))
a_in  = int(R["a_in"].replace(",",""));  a_out = int(R["a_out"].replace(",",""))
b_in  = int(R["b_in"].replace(",",""));  b_out = int(R["b_out"].replace(",",""))
a_turns, b_turns = 6, 2

print("="*78); print("1. 실측에서 turn_growth_tok 역산"); print("="*78)
print(f"  페르소나 A: {a_turns}턴, 입력 누계 {a_in:,}tok, 출력 누계 {a_out:,}tok")
print(f"  페르소나 B: {b_turns}턴, 입력 누계 {b_in:,}tok, 출력 누계 {b_out:,}tok")

# 입력 누계 = sum_{i=1..n} (base + (i-1)*g)  =  n*base + g*n(n-1)/2
# base는 B의 1턴 입력으로 근사(스펙 포함 최초 프롬프트)
base = b_in // b_turns
n = a_turns
g = (a_in - n*base) / (n*(n-1)/2)
print(f"\n  base(최초 프롬프트) ≈ {base:,}tok  (B 입력누계/{b_turns}턴)")
print(f"  → 등차 누적 가정으로 역산한 턴당 증가분 g = {g:,.0f} tok")

avg_out = a_out / a_turns
print(f"  참고: A의 턴당 평균 출력 = {avg_out:,.0f} tok")
print(f"        g가 평균출력의 {g/avg_out:.1f}배 — 출력 외에 파일 재첨부·"
      f"사용자 발화가 함께 쌓인 것")

print("\n" + "="*78)
print("2. 역산값으로 모델이 실측을 재현하는가 (검증)")
print("="*78)
GROWTH = int(round(g / 100.0) * 100)
print(f"  turn_growth_tok = {GROWTH:,} (반올림) 로 고정하고 재계산")
# A는 사다리 없음 = 전체 재출력 반복. router의 'retry'는 출력을 조이므로
# 대조군으로 직접 계산한다.
tin, tot = base, 0.0
for i in range(a_turns):
    tot += cost_of(Tier.MID, tin, int(avg_out))
    tin += GROWTH
print(f"  모델 재현값        ${tot:.4f}")
print(f"  실측 페르소나 A    ${float(R['a_cost']):.4f}")
err = abs(tot-float(R['a_cost']))/float(R['a_cost'])*100
print(f"  오차               {err:.1f}%")
print(f"\n  {'>>> 재현 성공 — 이 g를 쓸 수 있다' if err < 15 else '>>> 오차 큼 — 가정 재검토'}")

print("\n" + "="*78)
print("3. 누적을 반영한 전략 비교 (rework_cost turn_growth_tok 사용)")
print("="*78)
print(f"  {'실패':<5}{'제자리':>11}{'사다리':>11}{'배수':>8}   {'(누적 0일 때 배수)':>18}")
for f_ in (1,2,3,4,5,6):
    r0 = rework_cost("버그 수정", base, 2500, f_, strategy="retry")["usd"]
    e0 = rework_cost("버그 수정", base, 2500, f_, strategy="escalate")["usd"]
    r  = rework_cost("버그 수정", base, 2500, f_, strategy="retry",
                     turn_growth_tok=GROWTH)["usd"]
    e  = rework_cost("버그 수정", base, 2500, f_, strategy="escalate",
                     turn_growth_tok=GROWTH)["usd"]
    print(f"  {f_}회 {r:>10.4f} {e:>10.4f} {r/e:>7.2f}배 {r0/e0:>17.2f}배")

print("\n  → 누적을 넣으면 사다리 우위가 커진다. 리셋이 누적을 끊기 때문.")
print("     특히 실패 3회의 '역전'이 사라지는지 확인할 것.")
