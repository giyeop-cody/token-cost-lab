# -*- coding: utf-8 -*-
"""의도 불일치 분류·승격 검증."""
import sys
sys.path.insert(0, "/home/user/tcl/agent_setup")
from intent_guard import (classify_mismatch, MISMATCH_KINDS, ACLedger,
                          preflight_cost, preflight_prompt)

G, R, N = "\033[32m", "\033[31m", "\033[0m"
n = f = 0
def ck(c, m):
    global n, f
    n += 1
    if not c:
        f += 1
        print(f"  {R}FAIL{N} {m}")

print("1. 분류 정확도")
cases = [
    ("아직도 그 방식이네 아까 말한 대로", "stale"),
    ("여전히 예전 방식인데", "stale"),
    ("그거 말고 결제 부분만 건드려줘", "scope"),
    ("다른 파일은 손대지 마", "scope"),
    ("너무 많이 바꿨어", "scope"),
    ("색이 너무 촌스러운데", "taste"),
    ("말투가 어색해", "taste"),
    ("우리 팀은 원래 이 컨벤션 쓰는데", "assumption"),
    ("기존 규칙을 따라야지", "assumption"),
    ("이 구조로는 성능이 안 나와", "reasoning"),
    ("이거 로직이 잘못됐어", "reasoning"),
]
for text, want in cases:
    got, _ = classify_mismatch(text)
    ck(got == want, f"'{text}' → {got} (기대 {want})")

print("2. 신호 없으면 unknown — 추측하지 않는다")
for text in ["음 다시", "아니야", "다시 해줘"]:
    got, _ = classify_mismatch(text)
    ck(got == "unknown", f"'{text}' → {got} (기대 unknown)")

print("3. 맥락 오염이 섞이면 우선한다")
got, _ = classify_mismatch("아직도 색이 촌스러운데")
ck(got == "stale", f"복합 신호 우선순위 오류: {got}")

print("4. 티어를 올리는 종류는 reasoning 하나뿐")
ups = [k for k, v in MISMATCH_KINDS.items() if v["tier_up"]]
ck(ups == ["reasoning"], f"티어 상승 종류 오류: {ups}")

print("5. 승격 — 취향과 중복은 제외")
led = ACLedger()
ck(led.promote("우리 팀은 원래 이 컨벤션 쓰는데") is not None, "전제 승격 실패")
ck(led.promote("우리 팀은 원래 이 컨벤션 쓰는데") is None, "중복이 승격됨")
ck(led.promote("색이 너무 촌스러운데") is None, "취향이 승격됨")
ck(led.promote("음 다시") is None, "unknown이 승격됨")
ck(len(led.promoted) == 1, f"승격 수 오류: {len(led.promoted)}")
ck("컨벤션" in led.as_checklist(), "체크리스트에 근거 누락")

print("6. preflight는 B 1칸보다 두 자릿수 싸다")
ck(preflight_cost("small") < 0.0697 / 100, f"preflight 과다: {preflight_cost('small')}")
ck("세 줄" in preflight_prompt("x") or "3)" in preflight_prompt("x"),
   "preflight 프롬프트에 상한이 없다")

print("=" * 60)
print(f"  {n}건 중 {G if not f else R}{n-f} PASS{N} / {f} FAIL")
