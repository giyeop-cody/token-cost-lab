# -*- coding: utf-8 -*-
"""축소 사다리 · 입력 누적 · 조건부 tier-up 회귀 테스트."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from router import (rework_cost, cost_of, Tier, looks_rejected, looks_symptom,
                    RESET_PRIME_TOK)
from ladder_b import (IntentTracker, INTENT_LADDER, LEAN_LADDER,
                      CONDITIONAL_TIER_UP, rung_cost, _content_words)

P, F, cases = 0, 0, []
def ck(name, cond, note=""):
    global P, F
    if cond: P += 1; cases.append(("PASS", name, note))
    else:    F += 1; cases.append(("FAIL", name, note))

GROWTH, BASE = 4700, 1419

# ── 1. 하위 호환 — 기본값에서 기존 수치가 변하지 않는다 ──────────
ck("retry 기본값 불변",
   abs(rework_cost("버그 수정", 1800, 2500, 4, strategy="retry")["usd"] - 0.13625) < 1e-6)
ck("escalate 기본값 불변",
   abs(rework_cost("버그 수정", 1800, 2500, 4, strategy="escalate")["usd"] - 0.1106) < 1e-3)
ck("topfirst 기본값 불변",
   abs(rework_cost("버그 수정", 1800, 2500, 4, strategy="topfirst")["usd"] - 0.4200) < 1e-3)
ck("rung_cost carried 기본 0이면 불변",
   abs(rung_cost(Tier.MID, 1800, reset=False, scope="file") - 0.0286) < 1e-4)
ck("IntentTracker 기본 사다리는 7칸",
   IntentTracker().max_rungs == len(INTENT_LADDER) == 7)

# ── 2. 입력 누적 ────────────────────────────────────────────
g0 = rework_cost("버그 수정", BASE, 2500, 4, strategy="retry")["usd"]
g1 = rework_cost("버그 수정", BASE, 2500, 4, strategy="retry",
                 turn_growth_tok=GROWTH)["usd"]
ck("누적을 켜면 비용이 오른다", g1 > g0, f"${g0:.4f} → ${g1:.4f}")

tr = rework_cost("버그 수정", BASE, 2500, 4, strategy="escalate",
                 turn_growth_tok=GROWTH)["trail"]
resets = [s for s in tr if s["reset"]]
ck("리셋 칸에서 누적이 0으로 끊긴다",
   all(s["carried"] == 0 for s in resets), f"리셋 {len(resets)}칸")
ck("비리셋 칸은 누적이 쌓인다",
   any(s["carried"] > 0 for s in tr if not s["reset"]))

# 역전 해소: 누적 반영 시 모든 실패 횟수에서 사다리가 싸다
rev = []
for f_ in range(1, 7):
    r = rework_cost("버그 수정", BASE, 2500, f_, strategy="retry",
                    turn_growth_tok=GROWTH)["usd"]
    e = rework_cost("버그 수정", BASE, 2500, f_, strategy="escalate",
                    turn_growth_tok=GROWTH)["usd"]
    if e >= r: rev.append(f_)
ck("누적 반영 시 역전 구간 없음", not rev, f"역전={rev}")

# 사용자 요구: 짧은 리워크(1~2턴)에서도 이득
for f_ in (1, 2):
    r = rework_cost("버그 수정", BASE, 2500, f_, strategy="retry",
                    turn_growth_tok=GROWTH)["usd"]
    e = rework_cost("버그 수정", BASE, 2500, f_, strategy="escalate",
                    turn_growth_tok=GROWTH)["usd"]
    ck(f"{f_}턴 리워크에서도 사다리가 이득", e < r, f"${r:.4f} → ${e:.4f}")

# ── 3. 축소 사다리 ──────────────────────────────────────────
ck("LEAN_LADDER는 3칸", len(LEAN_LADDER) == 3)
ck("LEAN에 tier-up 상시 칸 없음",
   not any(r["step"] == "tier-up" for r in LEAN_LADDER))
ck("LEAN 마지막은 respec", LEAN_LADDER[-1].get("respec") is True)
ck("LEAN에 reset 칸 있음", any(r["reset"] for r in LEAN_LADDER))
ck("ladder 교체 시 max_rungs 자동 조정",
   IntentTracker(ladder=LEAN_LADDER).max_rungs == 3)

# ── 4. 조건부 tier-up ───────────────────────────────────────
t = IntentTracker(ladder=LEAN_LADDER)
t.observe("결제 재시도 로직 만들어줘")
d = t.observe("이거 말고 다시", mismatch_kind="reasoning")
ck("reasoning이면 tier-up 발동", d["step"] == "tier-up" and d["tier"] is Tier.LARGE)

t2 = IntentTracker(ladder=LEAN_LADDER)
t2.observe("결제 재시도 로직 만들어줘")
d2 = t2.observe("이거 말고 다시", mismatch_kind="taste")
ck("taste면 tier-up 안 함", d2["step"] == "widen" and d2["tier"] is Tier.MID)

t3 = IntentTracker(ladder=LEAN_LADDER)
t3.observe("결제 재시도 로직 만들어줘")
d3 = t3.observe("이거 말고 다시")
ck("kind 미지정이면 기본 사다리대로", d3["step"] == "widen")

t4 = IntentTracker(ladder=INTENT_LADDER)
t4.observe("결제 재시도 로직 만들어줘")
d4 = t4.observe("이거 말고 다시", mismatch_kind="reasoning")
ck("7칸 사다리에는 조건부 tier-up 미적용", d4["step"] == "widen")

# ── 5. 트리거 보강 (실발화 기준) ────────────────────────────
ck("'복잡한 거 말고' 검출", looks_rejected("아니 이렇게 복잡한 거 말고... 그냥 html 파일 하나로"))
ck("'처음부터 심플하게 다시' 검출", looks_rejected("그냥 처음부터 심플하게 다시 만들어줘"))
ck("증상신고 검출", looks_symptom("저장이 안 되는 것 같은데? 새로고침하면 사라져"))
ck("요청어미는 증상신고 아님", not looks_symptom("정렬이 안 되는 케이스도 테스트에 넣어줘"))
ck("요청어미2 배제", not looks_symptom("구형 브라우저에서 안 되는 문법은 피해줘"))

ART = _content_words("메모장 저장 목록 클릭 새로고침 html 파일")
t5 = IntentTracker(ladder=LEAN_LADDER)
t5.observe("단일 html 메모장 만들어줘")
d5 = t5.observe("저장이 안 되는 것 같은데? 새로고침하면 사라져", artifact_terms=ART)
ck("증상신고+산출물겹침 → 에스컬레이션", d5["action"] == "escalate" and d5.get("symptom"))

t6 = IntentTracker(ladder=LEAN_LADDER)
t6.observe("단일 html 메모장 만들어줘")
d6 = t6.observe("에러 핸들링 추가해줘", artifact_terms=ART)
ck("신규 지시는 에스컬레이션 안 함", d6["action"] == "proceed")

print("="*60)
for st, name, note in cases:
    if st == "FAIL":
        print(f"  {st}  {name}  {note}")
print(f"  {P+F}건 중 {P} PASS / {F} FAIL")
print("="*60)
sys.exit(1 if F else 0)
