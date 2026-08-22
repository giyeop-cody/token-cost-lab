# -*- coding: utf-8 -*-
"""축소 사다리(3칸) vs 기존(7칸) — 실로그와 누적 반영 비용으로 검증."""
import sys, re, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"agent_setup"))
from ladder_b import IntentTracker, INTENT_LADDER, LEAN_LADDER, rung_cost, _content_words
from router import Tier, rework_cost

GROWTH = 4700          # analysis/calibrate_growth.py 역산값 (실측 오차 5.8%)
BASE   = 1419          # 최초 프롬프트 (B 입력누계/2턴)

t = (ROOT/"demo/transcripts/persona_A_wasteful.md").read_text(encoding="utf-8")
A = [re.sub(r'\n*---+\s*요청 컨텍스트.*','',m.group(1),flags=re.S).strip()
     for m in re.finditer(r'\*\*USER\*\*\s*\n+```\n(.*?)\n```', t, re.S)]
ART = _content_words("메모장 저장 목록 클릭 편집기 새로고침 localStorage 삭제 제목 본문 html 파일")

def replay(ladder, name):
    tr = IntentTracker(ladder=ladder)
    rows, carried, total = [], 0, 0.0
    for i, u in enumerate(A, 1):
        d = tr.observe(u, artifact_terms=ART)
        if d["action"] == "proceed":
            rows.append((i, d["step"], d["tier"].name, d["scope"], 0.0, "—"))
            continue
        c = rung_cost(d["tier"], BASE, reset=d["reset"], scope=d["scope"],
                      carried_tok=carried)
        total += c
        carried = 0 if d["reset"] else carried + GROWTH
        rows.append((i, d["step"], d["tier"].name, d["scope"], c,
                     "리셋" if d["reset"] else f"누적{carried:,}"))
    print(f"\n[{name}]")
    print(f"  {'턴':<3}{'칸':<11}{'티어':<7}{'범위':<8}{'비용':>9}   비고")
    for r in rows:
        print(f"  {r[0]:<3}{r[1]:<11}{r[2]:<7}{r[3]:<8}"
              f"{('$'+format(r[4],'.4f')) if r[4] else '—':>9}   {r[5]}")
    print(f"  {'합계':<29}{'$'+format(total,'.4f'):>9}")
    return total

print("="*78)
print("1. 실로그 6턴 재생 — 7칸 vs 3칸")
print("="*78)
full = replay(INTENT_LADDER, "기존 7칸 INTENT_LADDER")
lean = replay(LEAN_LADDER,   "축소 3칸 LEAN_LADDER")
print(f"\n  >>> 축소가 ${full-lean:.4f} 저렴 ({full/lean:.2f}배)"
      if lean < full else f"\n  >>> 축소가 ${lean-full:.4f} 더 비쌈")

print("\n" + "="*78)
print("2. 누적 반영 후 '실패 3회 역전'이 해소됐는가")
print("="*78)
print(f"  {'실패':<5}{'제자리':>10}{'사다리':>10}{'배수':>8}")
bad = []
for f_ in range(1, 7):
    r = rework_cost("버그 수정", BASE, 2500, f_, strategy="retry",
                    turn_growth_tok=GROWTH)["usd"]
    e = rework_cost("버그 수정", BASE, 2500, f_, strategy="escalate",
                    turn_growth_tok=GROWTH)["usd"]
    flag = "  ← 역전" if e >= r else ""
    if e >= r: bad.append(f_)
    print(f"  {f_}회{r:>10.4f}{e:>10.4f}{r/e:>7.2f}배{flag}")
print(f"\n  역전 구간: {bad if bad else '없음'}   (누적 미반영 시에는 3회에서 역전)")

print("\n" + "="*78)
print("3. 사용자 요구 검증 — '짧은 리워크(1~2턴)에서도 이득'")
print("="*78)
for f_ in (1, 2):
    r = rework_cost("버그 수정", BASE, 2500, f_, strategy="retry",
                    turn_growth_tok=GROWTH)["usd"]
    e = rework_cost("버그 수정", BASE, 2500, f_, strategy="escalate",
                    turn_growth_tok=GROWTH)["usd"]
    print(f"  {f_}턴: 제자리 ${r:.4f} → 사다리 ${e:.4f}  "
          f"{'이득 ' + format((1-e/r)*100,'.0f') + '%' if e<r else '손해'}")

print("\n" + "="*78)
print("4. 반증 시도 — 축소 사다리가 지는 경우는 없는가")
print("="*78)
print("""  축소는 tier-up을 뺐다. 그러면 '진짜로 모델 능력이 부족한 작업'에서는
  축소가 영영 못 풀고 respec까지 가서 사람을 부를 것이다. 그 경우를 센다.""")
# 시나리오: reasoning 계열 — 티어를 올려야만 풀리는 작업
# 7칸: widen(실패) → tier-up(성공)   = 2칸
# 3칸: widen(실패) → reset(실패) → respec(사람 호출)
full_solve = (rung_cost(Tier.MID,   BASE, reset=False, scope="file", carried_tok=0)
            + rung_cost(Tier.LARGE, BASE, reset=False, scope="file", carried_tok=GROWTH))
lean_fail  = (rung_cost(Tier.MID,   BASE, reset=False, scope="file", carried_tok=0)
            + rung_cost(Tier.MID,   BASE, reset=True,  scope="unit")
            + rung_cost(Tier.MID,   BASE, reset=True,  scope="respec"))
HUMAN = 0.50   # 사람이 스펙 다시 잡는 시간의 기회비용(보수적 가정 — 라벨 필요)
print(f"\n  [티어를 올려야만 풀리는 작업 = reasoning 계열]")
print(f"    7칸: widen 실패 → tier-up 성공       ${full_solve:.4f}")
print(f"    3칸: widen → reset → respec(사람)    ${lean_fail:.4f} + 사람시간")
print(f"    → 토큰만 보면 3칸이 ${full_solve-lean_fail:.4f} 싸지만,")
print(f"      사람을 부르는 비용(가정 ${HUMAN:.2f})을 더하면 "
      f"${lean_fail+HUMAN:.4f} > ${full_solve:.4f} 로 **역전**")
print(f"\n  >>> 결론: tier-up을 완전히 삭제하면 안 된다.")
print(f"      의도불일치 분류가 'reasoning'으로 판정한 경우에만 남기는")
print(f"      **조건부 tier-up**이 옳다. 5종 중 1종이므로 상시 칸에서는 뺀다.")
