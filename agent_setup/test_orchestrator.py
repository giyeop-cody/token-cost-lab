# -*- coding: utf-8 -*-
"""A+B 결합 실행기 검증."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestrator import Orchestrator, _max_tier
from router import Tier
from ladder_b import IntentTracker, INTENT_LADDER, LEAN_LADDER

G, R, N = "\033[32m", "\033[31m", "\033[0m"
n = f = 0
def ck(c, m):
    global n, f
    n += 1
    if not c:
        f += 1
        print(f"  {R}FAIL{N} {m}")

BASE = "결제 실패 재시도 로직 구현해줘"

print("1. 티어 하한 — B는 A가 도달한 티어 아래로 안 내려간다")
o = Orchestrator()
o.user_turn("T", BASE)
for ok in [False, False, False, True]:
    o.inner("T", ac_passed=ok)
ck(o.tasks["T"].tier_floor is Tier.LARGE, "A가 large 도달 기록 실패")
r = o.user_turn("T", "결제 재시도 부분 다시 좀 해줘")
ck(r["tier"] is Tier.LARGE, "B 1칸이 mid로 퇴보")
ck(_max_tier(Tier.LARGE, Tier.MID) is Tier.LARGE, "_max_tier 오동작")
ck(_max_tier(Tier.EXTERNAL, Tier.MID) is Tier.MID, "EXTERNAL 처리 오류")

print("2. 생략형이 섞여도 사다리가 초기화되지 않는다 (앵커)")
# 축소 전 7칸 사다리로의 회귀 — 기본(lean)과 동작이 달라야 하는 경로.
o = Orchestrator(intent=IntentTracker(ladder=INTENT_LADDER))
cmds = [BASE, "결제 재시도 부분 다시 좀 해줘", "그 결제 재시도 다시",
        "결제 쪽 다시", "이거 다시", "아직도 아니야 결제 재시도 다시",
        "그 결제 로직 다시 좀", "결제 재시도 또 다시"]
layers = []
for c in cmds:
    r = o.user_turn("T", c)
    layers.append(r["layer"])
    if r["action"] == "respec":
        break
    o.inner("T", ac_passed=True)
ck(layers[0] == "A", "첫 턴이 A가 아님")
ck(all(l == "B" for l in layers[1:]), f"중간에 A로 리셋됨: {layers}")
ck(len(layers) == 8, f"7칸을 다 못 감: {len(layers)}")
ck(abs(o.tasks["T"].cost - 0.5149) < 0.001,
   f"결합 상한이 B 단독과 불일치: {o.tasks['T'].cost:.4f}")

print("3. 새 의도는 둘 다 초기화한다")
o = Orchestrator()
o.user_turn("T2", BASE)
o.inner("T2", ac_passed=True)
o.user_turn("T2", "결제 재시도 부분 다시 좀 해줘")
o.inner("T2", ac_passed=True)
r = o.user_turn("T2", "로그인 화면 CSS 좀 고쳐줘")
ck(r["layer"] == "A", "새 의도인데 B가 돌았다")
ck(r["tier"] is not Tier.LARGE, "새 의도에 난이도가 이월됐다")

print("4. A 단독 경로 — 사용자 턴을 태우지 않는다")
o = Orchestrator()
o.user_turn("T3", BASE)
for ok in [False, False, True]:
    o.inner("T3", ac_passed=ok)
ck(o.tasks["T3"].turns == 1, "A가 사용자 턴을 태웠다")
ck(sum(1 for t in o.tasks["T3"].trace if t["layer"] == "B") == 0, "B가 돌았다")

print("5. respec은 마지막에 한 번, 비용 0 (7칸 사다리 회귀)")
o = Orchestrator(intent=IntentTracker(ladder=INTENT_LADDER))
acts = []
for c in cmds:
    r = o.user_turn("T4", c)
    acts.append(r["action"])
    if r["action"] == "respec":
        ck(r["cost"] == 0.0, "respec에 비용이 붙었다")
        break
    o.inner("T4", ac_passed=True)
ck(acts.count("respec") == 1 and acts[-1] == "respec", f"respec 위치 오류: {acts}")

print("6. 기본(lean) 오케스트레이터 — 3칸 + 조건부 tier-up")
# 사다리 축소 적용 후 라이브 기본값: 3칸, 그리고 classify_mismatch 배선으로
# 조건부 tier-up이 실제로 동작해야 한다.
ol = Orchestrator()
ck(ol.intent.max_rungs == len(LEAN_LADDER) == 3, "기본 사다리는 lean(3칸)")
olayers = []
for c in cmds:                       # 7칸에선 8턴 걸리던 경로
    r = ol.user_turn("T6", c)
    olayers.append(r["action"])
    if r["action"] == "respec":
        break
    ol.inner("T6", ac_passed=True)
ck(olayers[-1] == "respec", f"3칸에서도 respec 도달: {olayers}")
ck(len(olayers) < len(cmds), f"full(8턴)보다 빨리 소진: {len(olayers)}턴")

# 조건부 tier-up: reasoning 반복 → large
o7 = Orchestrator()
o7.user_turn("T7", BASE)
r7 = o7.user_turn("T7", "결제 재시도 로직이 성능이 너무 느려서 다시 짜줘")
ck(r7["tier"] is Tier.LARGE, f"repeat+reasoning → large (실제 {r7['tier']})")

# 취향(taste) 반복 → tier-up 없음(mid 유지)
o8 = Orchestrator()
o8.user_turn("T8", BASE)
r8 = o8.user_turn("T8", "결제 재시도 로직이 색감이 별로야 다시 짜줘")
ck(r8["tier"] is Tier.MID, f"repeat+taste → mid 유지 (실제 {r8['tier']})")

print("=" * 60)
print(f"  {n}건 중 {G if not f else R}{n-f} PASS{N} / {f} FAIL")

raise SystemExit(1 if f else 0)
