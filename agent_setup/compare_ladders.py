"""사다리 A vs B — 같은 원가 모델로 나란히 세운다.

A = router.escalate        트리거: 내부 검증 실패(테스트/AC)
B = ladder_b.IntentTracker 트리거: 사용자가 같은 의도를 반복

둘은 경쟁하지 않는다. 잡는 실패의 종류가 다르다.
이 스크립트는 그 차이를 숫자로 만든다.
"""

from __future__ import annotations

import sys

from router import (
    FIRST_OUT_TOK,
    Decision,
    Kind,
    ReworkTracker,
    looks_rejected,
    rework_cost,
    Tier,
    cost_of,
    route,
)
import ladder_b as B

TASK = "결제 실패 재시도 로직 구현해줘"
TOK_IN, TOK_OUT = 1800, 2500

O, G, Y, R, D, N = "\033[1m", "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m"


def hr(c="─"):
    print(D + c * 78 + N)


def h(t):
    print(f"\n{O}{t}{N}")
    hr()


# ── 1. 트리거 비교 ────────────────────────────────────────────────────
h("1. 무엇이 사다리를 올리는가")

print(f"  {O}A 사다리{N}  트리거 = 테스트/AC 실패")
print(f"          {D}에이전트가 스스로 감지. 사용자 턴을 소모하지 않는다.{N}")
print(f"          {D}결과물이 사용자에게 나가기 전에 이미 고쳐져 있다.{N}")
print()
print(f"  {O}B 사다리{N}  트리거 = 사용자가 같은 의도를 반복")
print(f"          {D}결과물이 한 번 나갔고, 사용자가 보고 다시 시켰다.{N}")
print(f"          {D}한 칸당 사용자 턴 하나를 태운다.{N}")

# ── 2. 의도 감지가 실제로 되는가 ──────────────────────────────────────
h("2. B의 전제 — '같은 의도'를 문자열이 달라도 잡아내는가")

cases = [
    ("결제 실패 재시도 로직 구현해줘",
     "결제 재시도 부분 다시 좀 해줘", True),
    ("결제 실패 재시도 로직 구현해줘",
     "아까 그 재시도 구현 말인데 결제 쪽 다시 만들어줘", True),
    ("결제 실패 재시도 로직 구현해줘",
     "이거 말고", True),                       # 명시적 반려
    ("결제 실패 재시도 로직 구현해줘",
     "로그인 화면 CSS 좀 고쳐줘", False),        # 명확히 다른 의도
    ("결제 실패 재시도 로직 구현해줘",
     "재시도 횟수를 3회로 바꿔줘", False),       # 후속 수정이지 반복 아님
]
ok = 0
for a, b, want in cases:
    same, sim = B.same_intent(a, b)
    hit = same or looks_rejected(b)
    mark = f"{G}✓{N}" if hit == want else f"{R}✗{N}"
    ok += hit == want
    label = "같은 의도" if want else "다른 의도"
    print(f"  {mark} [{label}] sim={sim:<6} {D}{b[:36]}{N}")
print(f"\n  의도 판정 {ok}/{len(cases)} 정확")

# ── 3. 같은 실패를 두 사다리로 각각 처리 ──────────────────────────────
h("3. 같은 작업이 4번 어긋났을 때 — 누적 비용")

# A: 내부 실패 4회. 덱과 같은 수치를 쓰려면 반드시 router.rework_cost를
# 그대로 쓴다 — 범위별 입력 배수와 apply_with(상위 진단 + 하위 적용)를
# 손으로 다시 짜면 값이 어긋난다(실제로 한 번 어긋났다).
a = rework_cost(TASK, TOK_IN, TOK_OUT, fails=4, strategy="escalate")
a_rows, a_cum = [], 0.0
for t in a["trail"]:
    a_cum += t["usd"]
    a_rows.append((f"{t['attempt']} {t['step']}", t["tier"],
                   t["out_tok"], t["usd"], a_cum))

# B: 사용자가 같은 의도를 4번 반복.
it = B.IntentTracker()
cmds = [
    TASK,
    "결제 재시도 그거 다시 해줘",
    "재시도 로직 결제 쪽 다시",
    "그 결제 실패 재시도 다시 좀",
    "결제 재시도 구현 다시",
]
b_rows, b_cum = [], 0.0
for i, cmd in enumerate(cmds, 1):
    r = it.observe(cmd)
    if r["action"] == "respec":
        b_rows.append((f"{i} respec", "—", 0, 0.0, b_cum))
        break
    c = B.rung_cost(r["tier"], TOK_IN, reset=r.get("reset", False),
                    scope=r["scope"])
    b_cum += c
    b_rows.append((f"{i} {r['step']}", r["tier"].value, FIRST_OUT_TOK, c, b_cum))

print(f"  {O}A — 내부 실패 트리거{N}")
print(f"  {D}{'칸':<12}{'티어':<8}{'출력':>7}{'비용':>10}{'누적':>11}{N}")
for s, t, o, c, cum in a_rows:
    print(f"  {s:<12}{t:<8}{o:>7}{'$%.4f' % c:>10}{'$%.4f' % cum:>11}")

print(f"\n  {O}B — 사용자 반복 트리거{N}")
print(f"  {D}{'칸':<12}{'티어':<8}{'출력':>7}{'비용':>10}{'누적':>11}{N}")
for s, t, o, c, cum in b_rows:
    print(f"  {s:<12}{t:<8}{o:>7}{'$%.4f' % c:>10}{'$%.4f' % cum:>11}")

print(f"\n  A 상한 {G}${a_cum:.4f}{N}   B 상한 {Y}${b_cum:.4f}{N}"
      f"   → B가 {b_cum / a_cum:.2f}×")
print(f"  {D}B가 비싼 이유: 매 칸이 사용자에게 나갈 완성물이라{N}")
print(f"  {D}출력을 900으로 못 조인다({FIRST_OUT_TOK}토큰 전액).{N}")

# ── 4. 결정적 차이 — 서로 못 잡는 실패 ────────────────────────────────
h("4. 서로 못 잡는 실패 (여기가 핵심)")

print(f"  {O}A가 놓치는 것 — 'AC는 통과했는데 원하는 게 아님'{N}")
print(f"    테스트 초록불 → escalate 호출 자체가 안 일어난다.")
print(f"    사용자가 다시 시킬 때까지 에이전트는 성공했다고 믿는다.")
print(f"    {G}→ B만 잡는다.{N}")
print()
print(f"  {O}B가 놓치는 것 — '사용자가 결과를 안 본 사이의 실패'{N}")
print(f"    사용자 턴이 와야 사다리가 돈다. 배치·비동기 작업은")
print(f"    사용자가 몇 시간 뒤에 본다. 그동안 실패가 방치된다.")
print(f"    {G}→ A만 잡는다.{N}")

# ── 5. 결합 ───────────────────────────────────────────────────────────
h("5. 둘을 겹쳤을 때")

# 난제 35% 가정, A는 내부 실패의 78%를 흡수, 그중 AC통과-오답이 22% 남는다.
P_HARD = 0.35
A_CATCH = 0.78          # 내부 검증으로 잡히는 비율
SILENT = 0.22           # AC 통과했지만 의도와 다른 비율

only_a = P_HARD * A_CATCH
silent = P_HARD * SILENT
print(f"  난제 비율 {P_HARD:.0%} 가정")
print(f"    A가 자체 흡수      {only_a:.1%}  {D}사용자가 모르는 사이 해결{N}")
print(f"    AC 통과·의도 불일치 {silent:.1%}  {D}A는 영영 못 본다{N}")
print()
print(f"  A만: {silent:.1%}가 사용자에게 그대로 나간다.")
print(f"  A+B: A가 먼저 걸러내고, 남은 {silent:.1%}를 B가 사용자 턴에서 잡는다.")
print()
print(f"  {O}결합 시 B의 부담이 줄어든다{N} — B 단독이면 모든 실패가")
print(f"  사용자 턴을 태우지만, A가 앞단에서 {A_CATCH:.0%}를 흡수하면")
print(f"  B가 실제로 도는 횟수는 {SILENT:.0%}로 떨어진다.")

# A→B 순차: A가 자체 흡수한 건은 B가 안 돈다. B는 silent 비율에서만
# 돌고, 그때도 A가 이미 사다리를 다 쓴 뒤라 B는 상위 칸부터 시작한다.
# 기대비용으로 비교한다(상한 비교는 결합 구조를 왜곡한다).
b_rung_avg = (b_cum - b_rows[0][3]) / max(len(b_rows) - 1, 1)
e_a_only = a_cum * P_HARD                      # A만: 난제에서 사다리 소모
e_a_b = a_cum * P_HARD + b_rung_avg * silent   # A+B: silent에서만 B가 돔
e_b_only = b_cum * P_HARD                      # B만: 난제 전부를 사용자 턴으로

print(f"\n  {D}기대비용(작업 1건 평균, 난제 {P_HARD:.0%}){N}")
print(f"    B 단독   ${e_b_only:.4f}   {D}모든 실패가 사용자 턴을 태운다{N}")
print(f"    A 단독   ${e_a_only:.4f}   {R}silent {silent:.1%}는 미처리로 남는다{N}")
print(f"    A → B    ${e_a_b:.4f}   {G}silent까지 덮으면서 B 단독의 "
      f"{e_a_b / e_b_only:.0%}{N}")
print(f"\n  {D}상한 비교: A ${a_cum:.4f} · B ${b_cum:.4f} (B가 {b_cum / a_cum:.2f}×){N}")

hr("═")
print(f"{O}결론{N}")
print("  · A와 B는 대체재가 아니다. 트리거가 다르고, 놓치는 실패가 반대다.")
print(f"  · B는 칸당 평균 ${b_rung_avg:.4f}로 A보다 비싸다 —")
print("    사용자에게 나갈 완성물이라 출력 상한을 못 걸기 때문이다.")
print("  · 그래서 B를 1차 방어선으로 쓰면 안 된다. A로 먼저 흡수하고,")
print("    A가 구조적으로 못 보는 'AC 통과·의도 불일치'만 B가 맡는다.")
print("  · B의 마지막 칸(respec)은 비용 절감이 아니라 손실 차단이다.")
print("    같은 의도가 5번 반복되면 구현이 아니라 합의가 없는 것이다.")
