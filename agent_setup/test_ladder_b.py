"""사다리 B 검증 — 의도 감지기와 사다리 상태 기계.

감지기는 5개 사례로 튜닝했으므로, 여기서는 튜닝에 쓰지 않은
사례로 확인한다. 특히 **거짓 양성**(다른 의도를 반복으로 오인)이
치명적이다 — 사용자가 새 작업을 시켰는데 사다리가 올라가면
쓸데없이 비싼 티어로 처리된다.
"""
from __future__ import annotations

import sys

from router import Tier, looks_rejected
from ladder_b import IntentTracker, INTENT_LADDER, same_intent, _content_words

P = F = 0
def ck(cond, label):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  \033[31mFAIL\033[0m {label}")

def detect(prev, cur):
    same, _ = same_intent(prev, cur)
    return same or looks_rejected(cur)

BASE = "사용자 프로필 이미지 업로드 기능 구현해줘"

# ── 1. 같은 의도로 판정돼야 하는 재요청 (튜닝에 안 쓴 문장) ──────────
REPEAT = [
    "프로필 이미지 업로드 다시 구현해줘",
    "그 이미지 업로드 기능 다시",
    "아까 프로필 업로드 말인데 다시 해줘",
    "사용자 프로필 이미지 업로드 다시 만들어줘",
    "업로드 기능 프로필 이미지 쪽 다시 좀",
    "그 프로필 이미지 업로드 다시",
    "프로필 업로드 구현 다시 해줘",
    "이거 말고",
    "그게 아니라 다시",
    "방금 그 업로드 구현 다시",
]
print("1. 같은 의도 재요청")
for c in REPEAT:
    ck(detect(BASE, c), f"반복 미탐지: {c}")

# ── 2. 다른 의도로 판정돼야 하는 것 (거짓 양성 방지) ─────────────────
DIFFERENT = [
    "결제 모듈 리팩터링 해줘",
    "README 업데이트 해줘",
    "테스트 커버리지 올려줘",
    "업로드 용량 제한을 10MB로 바꿔줘",     # 후속 파라미터 수정
    "이미지 썸네일 생성도 추가해줘",         # 기능 추가(확장)
    "배포 스크립트 작성해줘",
    "로그 포맷 JSON으로 바꿔줘",
]
print("2. 다른 의도 (거짓 양성 방지)")
for c in DIFFERENT:
    ck(not detect(BASE, c), f"거짓 양성: {c}")

# ── 3. 사다리 진행 순서 ──────────────────────────────────────────────
print("3. 사다리 순서 — 사용자 설계 그대로인가")
it = IntentTracker(ladder=INTENT_LADDER)
it.observe(BASE)
steps = []
for c in REPEAT[:7]:
    r = it.observe(c)
    steps.append(r["step"])
ck(steps == ["widen", "tier-up", "widen-2", "repeat-1",
             "reset", "repeat-2", "respec"],
   f"사다리 순서: {steps}")
ck(steps.count("respec") == 1 and steps[-1] == "respec",
   "respec은 마지막에 한 번만")

it2 = IntentTracker(ladder=INTENT_LADDER)
it2.observe(BASE)
r1 = it2.observe("프로필 이미지 업로드 다시 구현해줘")
ck(r1["scope"] == "file", f"1칸: 범위 확장돼야 함 → {r1['scope']}")
ck(r1["tier"] == Tier.MID, f"1칸: 티어 유지돼야 함 → {r1['tier']}")
r2 = it2.observe("그 이미지 업로드 기능 다시")
ck(r2["tier"] == Tier.LARGE, f"2칸: 티어 올라야 함 → {r2['tier']}")
ck(r2.get("reset") is False, "2칸: 아직 리셋 아님")
r3 = it2.observe("아까 프로필 업로드 말인데 다시 해줘")
ck(r3["scope"] == "module", f"3칸: 범위 또 확장 → {r3['scope']}")
r4 = it2.observe("사용자 프로필 이미지 업로드 다시 만들어줘")
ck(r4["step"] == "repeat-1", f"4칸: 리셋 전 반복 → {r4['step']}")
ck(r4.get("reset") is False, "4칸: 아직 리셋 아님 — 맥락은 늦게 버린다")
ck(r4["scope"] != "respec", "중간 칸이 respec 범위로 가면 안 됨")
r5 = it2.observe("업로드 기능 프로필 이미지 쪽 다시 좀")
ck(r5.get("reset") is True, "5칸: 리셋이어야 함")
ck(r5["scope"] == "unit", f"5칸: 리셋은 범위를 되돌려야 함 → {r5['scope']}")
r6 = it2.observe("그 프로필 이미지 업로드 다시")
ck(r6["step"] == "repeat-2", f"6칸: 리셋 후 반복 → {r6['step']}")
ck(r6["tier"] == Tier.LARGE, "6칸: 티어는 리셋해도 유지")
r7 = it2.observe("프로필 업로드 구현 다시 해줘")
ck(r7["action"] == "respec", f"7칸: respec이어야 함 → {r7['action']}")

# ── 4. 새 의도가 오면 사다리가 초기화되는가 ──────────────────────────
print("4. 사다리 초기화")
it3 = IntentTracker(ladder=INTENT_LADDER)
it3.observe(BASE)
it3.observe("프로필 이미지 업로드 다시 구현해줘")   # 1칸 올라감
ck(it3.rung == 1, f"올라간 상태 확인 → rung={it3.rung}")
r = it3.observe("결제 모듈 리팩터링 해줘")           # 새 의도
ck(it3.rung == 0, f"새 의도 후 초기화돼야 함 → rung={it3.rung}")
ck(r["tier"] == Tier.MID, f"새 의도는 MID에서 시작 → {r['tier']}")
ck(it3._scope_i == 0, "새 의도는 범위도 초기화")

# ── 5. 리셋 이후에도 사다리를 다 쓰면 respec ─────────────────────────
print("5. 소진 처리")
it4 = IntentTracker(ladder=INTENT_LADDER)
it4.observe(BASE)
for c in REPEAT[:7]:
    it4.observe(c)
r = it4.observe("프로필 업로드 다시 해줘")
ck(r["action"] == "respec", f"소진 후에도 respec 유지 → {r['action']}")

# ── 5b. 생략형 재시도 (사람은 두 번째부터 짧게 말한다) ──────────────
print("5b. 생략형 재시도")
# BASE는 "사용자 프로필 이미지 업로드 기능 구현해줘"다.
# 생략형은 BASE의 내용어를 하나라도 물고 있거나 조응 표현이 있어야 한다.
for c in ["업로드 다시", "이거 다시", "프로필 다시 좀", "다시 해줘",
          "아까 그거 다시", "그 기능 다시"]:
    t = IntentTracker(ladder=INTENT_LADDER)
    t.observe(BASE)
    ck(t.observe(c)["step"] != "new-intent", f"생략형 미탐지: {c}")

# 생략형이라도 재시도 표시가 없으면 새 의도다
for c in ["썸네일도", "그럼 배포는", "테스트 커버리지"]:
    t = IntentTracker(ladder=INTENT_LADDER)
    t.observe(BASE)
    ck(t.observe(c)["step"] == "new-intent", f"재시도 표시 없는데 오탐: {c}")

# "다시"가 붙어도 명확히 다른 작업이면 새 의도
for c in ["타임아웃 값을 다시 계산해서 30초로 바꿔줘",
          "문서를 다시 정리해서 위키에 올려줘"]:
    t = IntentTracker(ladder=INTENT_LADDER)
    t.observe(BASE)
    ck(t.observe(c)["step"] == "new-intent", f"긴 다른 작업 오탐: {c}")

# ── 6. 내용어 추출 ───────────────────────────────────────────────────
print("6. 내용어 추출")
w = _content_words("사용자 프로필 이미지 업로드 기능 구현해줘")
ck("프로필" in w, "명사 보존")
ck("다시" not in _content_words("다시 해줘 좀"), "군더더기 제거")
ck("업로드" in _content_words("업로드를 다시"), "조사 제거")

print()
print("=" * 60)
c = "\033[32m" if F == 0 else "\033[31m"
print(f"  {P + F}건 중 {c}{P} PASS\033[0m / {F} FAIL")
print("=" * 60)
sys.exit(1 if F else 0)
