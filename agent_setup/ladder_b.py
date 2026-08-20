"""사다리 B — 사용자 의도 반복을 트리거로 삼는 에스컬레이션.

사다리 A(router.escalate)와 트리거가 다르다.

    A: 내부 검증 실패(테스트/AC)가 트리거. 에이전트가 스스로 감지하고
       같은 턴 안에서 올라간다. 사용자는 개입하지 않는다.

    B: 사용자가 "같은 의도"를 다시 말하는 것이 트리거. 결과물이 이미
       한 번 나갔고, 사용자가 그걸 보고 다시 시켰다는 뜻이다.

B의 사다리 순서(사용자 설계 그대로):

    명령 기록 → 재시도 맥락 감지 → 범위 확장 → (같은 의도) → 모델 상승
    → (같은 의도) → 범위 확장 → (반복) → 새 세션 → (반복) → 스펙 재정의

A와의 결정적 차이 두 가지:

  1. B의 한 칸은 **사용자 턴을 하나 태운다.** 결과물이 사용자 앞까지
     갔다가 반려된 것이므로, 그 턴의 출력은 이미 전액 지불됐다.
     A의 한 칸은 사용자가 모르는 사이에 지나간다.

  2. B는 **테스트가 통과하는 실패**를 잡는다. "동작은 하는데 원하는 게
     아닌" 결과는 AC가 초록불이라 A가 영영 감지하지 못한다.
     이건 B만 잡을 수 있다.

그래서 이 모듈은 A의 대체재가 아니다. 측정 결과는 compare_ladders.py 참조.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import re

from router import (
    FIRST_OUT_TOK,
    REWORK_OUT_TOK,
    RESET_PRIME_TOK,
    SCOPE_LADDER,
    Decision,
    Tier,
    _tier_up,
    cost_of,
    looks_rejected,
)

# ── 의도 반복 감지 ────────────────────────────────────────────────────
#
# "이전 명령을 재시도하라"는 신호는 두 가지 형태로 온다.
#
#   (a) 명시적 반려 — "이거 말고", "다시 해줘". router.looks_rejected 재사용.
#   (b) 무언의 재요청 — 불평 없이 같은 요청을 살짝 바꿔 다시 말한다.
#       이쪽이 실제로는 더 흔하고, 놓치면 사다리가 영영 안 돈다.
#
# (b)를 잡으려면 "같은 의도"를 판정해야 한다. 문자열 동일성으로는 안 된다.
# 사용자는 매번 다르게 쓴다. 그래서 내용어 집합의 자카드 유사도를 쓴다.

# 앞선 작업을 가리키는 조응 표현. 이게 있으면 내용어 겹침이 적어도
# "그 얘기 다시"라는 뜻이므로 문턱을 낮춘다.
_ANAPHORA = re.compile(
    r"(아까|방금|앞에서|이전에?|저번에?|그때|말인데|말이야|말고"
    r"|그\s*(거|건|것|작업|부분|코드)|위에\s*(거|것)|하던\s*(거|것))")

_STOP = {
    "좀", "다시", "이거", "그거", "저거", "해줘", "해", "주세요", "please",
    "the", "a", "an", "to", "of", "and", "그리고", "근데", "아니",
    "말고", "왜", "안", "못", "수", "것", "게", "거", "너무", "더",
    "제발", "일단", "그냥", "좀더", "다시한번",
}


def _tokenize(text: str) -> list[str]:
    """공백을 살린 정규화. router._norm은 공백까지 지우므로 쓸 수 없다."""
    return re.sub(r"[^\w가-힣\s]+", " ", text.lower()).split()


def _content_words(text: str) -> set[str]:
    """조사·군더더기를 걷어낸 내용어 집합."""
    toks = _tokenize(text)
    out: set[str] = set()
    for t in toks:
        t = t.strip(".,!?;:\"'()[]{}")
        # 한국어 조사 꼬리를 거칠게 떼어낸다 — 형태소 분석기 없이.
        for josa in ("으로", "에서", "에게", "까지", "부터", "이랑", "하고",
                     "은", "는", "이", "가", "을", "를", "에", "의", "도", "만"):
            if len(t) > len(josa) + 1 and t.endswith(josa):
                t = t[: -len(josa)]
                break
        # 용언 어미도 뗀다. "구현해줘"와 "구현"이 안 맞으면
        # 첫 명령(대개 "~해줘")과 재요청이 영영 안 겹친다.
        for eomi in ("해주세요", "해줘요", "해줘", "해주", "하기", "해라",
                     "했어", "한다", "하는", "해서", "어줘", "아줘", "해"):
            if len(t) > len(eomi) + 1 and t.endswith(eomi):
                t = t[: -len(eomi)]
                break
        if len(t) >= 2 and t not in _STOP:
            out.add(t)
    return out


def same_intent(a: str, b: str, threshold: float = 0.5) -> tuple[bool, float]:
    """두 명령이 같은 의도인가. (판정, 유사도)

    자카드가 아니라 **중첩 계수**(교집합 / 짧은 쪽)를 쓴다.
    재요청은 대개 짧게 다시 말하므로("결제 재시도 다시"),
    자카드는 길이 차이만으로 유사도를 깎아 같은 의도를 놓친다.

    추가로 공유 내용어 2개 이상을 요구한다 — 한 단어만 겹치는
    후속 수정("재시도 횟수를 3회로")을 반복으로 오인하지 않기 위해서다.
    """
    wa, wb = _content_words(a), _content_words(b)
    if not wa or not wb:
        return False, 0.0
    shared = wa & wb
    ov = len(shared) / min(len(wa), len(wb))
    if len(shared) < 2:
        return False, round(ov, 3)
    # 조응 표현이 있으면 문턱을 낮춘다. "아까 그거 다시"류는
    # 의도적으로 짧게 말하므로 내용어가 적게 겹친다.
    thr = threshold * 0.7 if _ANAPHORA.search(b) else threshold
    return ov >= thr, round(ov, 3)


# ── B 사다리 ──────────────────────────────────────────────────────────
#
# 사용자 설계 순서를 그대로 칸으로 옮긴다.
# A와 달리 첫 칸이 retry가 아니라 widen이다 — 사용자가 이미 한 번
# 결과를 보고 반려했으므로, 같은 범위로 또 하는 것은 같은 답을 부른다.

INTENT_LADDER = [
    dict(step="widen", scope_up=1, tier_up=0, reset=False,
         why="사용자가 결과를 보고 다시 시켰다. 같은 범위로 또 하면 "
             "같은 결과가 나온다. 모델은 그대로 두고 보는 범위를 넓힌다."),
    dict(step="tier-up", scope_up=0, tier_up=1, reset=False,
         why="범위를 넓혀도 같은 요청이 또 왔다. 이제 모델을 올린다."),
    dict(step="widen-2", scope_up=1, tier_up=0, reset=False,
         why="올린 모델로 범위를 한 번 더 넓힌다. 티어와 범위를 "
             "번갈아 올려 한쪽만 과하게 태우지 않는다."),
    dict(step="reset", scope_up=0, tier_up=0, reset=True,
         why="여기까지 왔다면 누적된 맥락 자체가 오염됐을 가능성이 높다. "
             "세션을 갈고 확정된 것만 이월한다."),
    dict(step="respec", scope_up=0, tier_up=0, reset=True, respec=True,
         why="같은 의도가 다섯 번 반복됐다. 구현 문제가 아니라 "
             "스펙이 합의되지 않은 것이다. 구현을 멈추고 스펙으로 되돌린다."),
]


@dataclass
class IntentTracker:
    """사용자 명령을 기록하고, 같은 의도의 반복을 세어 사다리를 올린다."""

    threshold: float = 0.5
    max_rungs: int = field(default=len(INTENT_LADDER))
    history: list[str] = field(default_factory=list)
    streak: int = 0            # 같은 의도가 연속으로 몇 번 왔나
    rung: int = 0              # 현재 올라간 칸 수
    _scope_i: int = 0
    _tier: Tier = Tier.MID

    def observe(self, command: str, *, prev_output: str = "") -> dict:
        """명령을 기록하고 에스컬레이션 여부를 판정한다.

        반환: {action, step, tier, scope, reason, similarity}
              action ∈ {"proceed", "escalate", "respec"}
        """
        prior = self.history[-1] if self.history else ""
        self.history.append(command)

        if not prior:
            self._tier = Tier.MID
            return dict(action="proceed", step="first", tier=self._tier,
                        scope=SCOPE_LADDER[self._scope_i],
                        similarity=0.0, reason="첫 명령 — 기록만 한다.")

        same, sim = same_intent(prior, command, self.threshold)
        # 명시적 반려어("이거 말고")는 유사도가 낮아도 재시도로 친다.
        explicit = looks_rejected(command)
        if not (same or explicit):
            self.streak = 0
            self.rung = 0
            self._scope_i = 0
            self._tier = Tier.MID
            return dict(action="proceed", step="new-intent", tier=self._tier,
                        scope=SCOPE_LADDER[self._scope_i], similarity=sim,
                        reason="새로운 의도 — 사다리를 초기화한다.")

        self.streak += 1
        if self.rung >= self.max_rungs:
            return dict(action="respec", step="exhausted", tier=self._tier,
                        scope="respec", similarity=sim,
                        reason="사다리를 다 썼다. 사람이 스펙을 다시 잡아야 한다.")

        rung = INTENT_LADDER[self.rung]
        self.rung += 1
        self._scope_i = min(self._scope_i + rung["scope_up"],
                            len(SCOPE_LADDER) - 1)
        for _ in range(rung["tier_up"]):
            self._tier = _tier_up(self._tier)

        return dict(
            action="respec" if rung.get("respec") else "escalate",
            step=rung["step"], tier=self._tier,
            scope=SCOPE_LADDER[self._scope_i], reset=rung["reset"],
            similarity=sim, explicit=explicit, reason=rung["why"],
        )


# ── B 한 칸의 비용 ────────────────────────────────────────────────────
#
# 여기가 A와 갈리는 지점이다. B의 칸은 사용자에게 나갈 결과물이라
# "진단 + diff"로 잘라낼 수 없다. 사용자는 완성된 답을 기대한다.
# 그래서 출력이 리워크 상한(900)이 아니라 첫 배정 상한(2500)에 가깝다.

# router.rework_cost와 동일한 규칙을 쓴다. 범위가 넓어지면 입력이
# 커지는 것은 두 사다리에 똑같이 적용돼야 비교가 성립한다.
SCOPE_MULT = {"unit": 1.0, "file": 1.6, "module": 2.4, "respec": 1.2}


def rung_cost(tier: Tier, tok_in: int, *, reset: bool, scope: str = "unit",
              user_facing: bool = True) -> float:
    """B 사다리 한 칸의 비용.

    user_facing=True면 출력 상한을 못 조인다 — 사용자에게 나갈
    완성물이라 "진단 + diff"로 대체할 수 없기 때문이다.
    """
    tin = int(tok_in * SCOPE_MULT[scope])
    if reset:
        tin += RESET_PRIME_TOK
    out = FIRST_OUT_TOK if user_facing else REWORK_OUT_TOK
    return cost_of(tier, tin, out)


__all__ = ["same_intent", "IntentTracker", "INTENT_LADDER", "rung_cost",
           "_content_words"]
