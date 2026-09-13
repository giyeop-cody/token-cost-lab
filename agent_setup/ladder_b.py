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
    looks_symptom,
)
from config import DEFAULT_LADDER

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
    r"|[그이요]\s*(거|건|것|작업|부분|코드)|위에\s*(거|것)|하던\s*(거|것))")

# 재시도를 뜻하는 표시. 이것만으로는 부족하지만(새 작업에도 "다시"가 붙는다)
# 짧은 생략형 명령을 맥락으로 해석할 때 필요조건으로 쓴다.
_RETRY_MARK = re.compile(r"(다시|또|한\s*번\s*더|재시도|되돌|롤백|엎)")

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

# 사용자 설계 원문:
#   범위 확장 → 모델 상승 → 범위 확장 → 반복 → 새 세션 → 반복 → 스펙 재정의
#
# "반복"이 두 번 나온다. 즉 (범위↑ / 티어↑) 사이클을 리셋 **전에** 한 번 더 돌고,
# 리셋 **후에** 또 돈 다음에야 respec으로 간다. 한 칸씩으로 압축하면
# 리셋이 너무 일찍 온다 — 리셋은 맥락을 버리는 행위라 늦을수록 좋다.
#
# 범위는 unit→file→module에서 천장을 친다(respec은 마지막 칸 전용).
# 천장에 닿으면 scope_up은 자동으로 무시되므로 티어만 올라간다.

INTENT_LADDER = [
    dict(step="widen", scope_up=1, tier_up=0, reset=False,
         why="사용자가 결과를 보고 다시 시켰다. 같은 범위로 또 하면 "
             "같은 결과가 나온다. 모델은 그대로 두고 보는 범위를 넓힌다."),
    dict(step="tier-up", scope_up=0, tier_up=1, reset=False,
         why="범위를 넓혀도 같은 요청이 또 왔다. 이제 모델을 올린다."),
    dict(step="widen-2", scope_up=1, tier_up=0, reset=False,
         why="올린 모델로 범위를 한 번 더 넓힌다. 티어와 범위를 번갈아 "
             "올려 한쪽만 과하게 태우지 않는다."),
    dict(step="repeat-1", scope_up=1, tier_up=1, reset=False,
         why="사용자 설계의 첫 번째 '반복'. 리셋은 누적 맥락을 버리는 "
             "행위라 되돌릴 수 없다 — 그 전에 현재 세션에서 쓸 수 있는 "
             "카드를 모두 쓴다."),
    dict(step="reset", scope_up=0, tier_up=0, reset=True,
         why="현 세션에서 할 수 있는 걸 다 했는데도 같은 요청이 온다. "
             "누적된 맥락 자체가 오염됐다고 보고 세션을 갈되, "
             "확정된 것만 이월한다."),
    dict(step="repeat-2", scope_up=1, tier_up=0, reset=False,
         why="사용자 설계의 두 번째 '반복'. 깨끗한 세션에서 다시 넓혀본다. "
             "맥락 오염이 원인이었다면 여기서 풀린다."),
    dict(step="respec", scope_up=0, tier_up=0, reset=True, respec=True,
         why="세션을 갈고 다시 넓혀도 같은 의도가 또 왔다. 구현 문제가 "
             "아니라 스펙이 합의되지 않은 것이다. 구현을 멈추고 "
             "사람에게 스펙을 다시 잡게 한다."),
]


# ── 축소 사다리 ─────────────────────────────────────────────
# 실로그 검증 결과 7칸 중 값을 한 이유가 확인된 칸은 둘뿐이었다.
#   - tier-up : 실로그 턴5에서 LARGE로 올렸으나 원인은 리스너 재등록 누락.
#               모델 능력과 무관했다. 티어 상승이 정답인 건 5종 중
#               reasoning 하나뿐이다.
#   - widen-2 / repeat-1 / repeat-2 : 실패 3회 구간에서 사다리를
#               제자리 반복보다 비싸게 만드는 주범(0.99배 역전).
# 남긴 것은 widen(범위 확대)과 respec(구현 중단), 그리고 그 사이에
# 리셋 한 칸이다. 리셋은 입력 누적을 끊어 절감의 17%를 담당한다.
#
# tier-up은 삭제가 아니라 **조건부**로 남긴다. 완전히 빼면 정말로 모델
# 능력이 부족한 작업(reasoning 계열)에서 respec까지 내려가 사람을 부르게
# 되는데, 사람 시간을 넣고 계산하면 $0.5832 > $0.1377로 역전한다.
# 그래서 의도불일치 분류가 reasoning으로 판정한 경우에만 이 칸을 끼운다.
CONDITIONAL_TIER_UP = dict(
    step="tier-up", scope_up=0, tier_up=1, reset=False,
    why="분류기가 'reasoning'으로 판정했다 — 범위나 맥락이 아니라 "
        "난이도가 원인인 유일한 종류다. 이때만 모델을 올린다.")

LEAN_LADDER = [
    dict(step="widen", scope_up=1, tier_up=0, reset=False,
         why="사용자가 결과를 보고 다시 시켰다. 같은 범위로 또 하면 "
             "같은 결과가 나온다. 모델은 그대로 두고 보는 범위를 넓힌다."),
    dict(step="reset", scope_up=0, tier_up=0, reset=True,
         why="넓혀도 같은 요청이 온다. 누적된 맥락이 오염됐다고 보고 "
             "세션을 갈되 확정된 것만 이월한다. 입력 누적이 여기서 끊긴다."),
    dict(step="respec", scope_up=0, tier_up=0, reset=True, respec=True,
         why="세션을 갈아도 같은 의도가 또 왔다. 구현 문제가 아니라 "
             "스펙이 합의되지 않은 것이다. 구현을 멈추고 스펙을 다시 잡는다."),
]


def default_ladder() -> list:
    """설정(config.DEFAULT_LADDER)에 맞는 기본 사다리를 반환한다.

    데코레이터/시연은 기본 인자를 평가할 때 한 번만 부른다.
    "lean"이면 3칸 축소 사다리, 그 외엔 7칸 원본 사다리.
    """
    return LEAN_LADDER if DEFAULT_LADDER == "lean" else INTENT_LADDER


@dataclass
class IntentTracker:
    """사용자 명령을 기록하고, 같은 의도의 반복을 세어 사다리를 올린다.

    ladder: 사용할 사다리. 기본은 config.DEFAULT_LADDER가 가리키는 사다리
        (현재 "lean" → 3칸 LEAN_LADDER). INTENT_LADDER(7칸)를 명시하면
        축소 적용 전 동작으로 되돌아간다.
    """

    threshold: float = 0.5
    ladder: list = field(default_factory=default_ladder)
    max_rungs: int = field(default=len(INTENT_LADDER))
    history: list[str] = field(default_factory=list)
    anchor: str = ""           # 현재 의도 묶음을 시작한 '내용 있는' 명령
    streak: int = 0            # 같은 의도가 연속으로 몇 번 왔나
    rung: int = 0              # 현재 올라간 칸 수
    _scope_i: int = 0
    _tier: Tier = Tier.MID

    def __post_init__(self) -> None:
        # ladder를 바꿔 넘겼는데 max_rungs가 기본값이면 길이를 맞춘다.
        if self.max_rungs == len(INTENT_LADDER) and self.ladder is not INTENT_LADDER:
            self.max_rungs = len(self.ladder)

    def observe(self, command: str, *, prev_output: str = "",
                artifact_terms: set[str] | None = None,
                mismatch_kind: str = "") -> dict:
        """명령을 기록하고 에스컬레이션 여부를 판정한다.

        artifact_terms: 직전 산출물이 다루는 개념어. 증상 신고
            ("저장이 안 돼")를 반려로 볼지 신규 지시로 볼지 가르는
            기준이다. 문장만으로는 안 갈린다 — 실측에서 텍스트 단독
            판정은 거짓양성 5/6이었고, 이 인자를 함께 쓰면 0/10이 된다.

        반환: {action, step, tier, scope, reason, similarity}
              action ∈ {"proceed", "escalate", "respec"}
        """
        # 직전 명령이 아니라 **앵커**(이 의도 묶음을 시작한 명령)와 비교한다.
        # 사람은 재요청을 점점 짧게 줄인다: "결제 재시도 다시" → "이거 다시".
        # 직전 것과만 비교하면 내용어가 없는 생략형 다음 턴에서 비교 대상이
        # 비어버려 사다리가 통째로 초기화된다. 앵커는 생략형으로 갱신하지 않는다.
        prior = self.anchor or (self.history[-1] if self.history else "")
        self.history.append(command)

        if not prior:
            self.anchor = command
            self._tier = Tier.MID
            return dict(action="proceed", step="first", tier=self._tier,
                        scope=SCOPE_LADDER[self._scope_i],
                        similarity=0.0, reason="첫 명령 — 기록만 한다.")

        same, sim = same_intent(prior, command, self.threshold)
        # 명시적 반려어("이거 말고")는 유사도가 낮아도 재시도로 친다.
        explicit = looks_rejected(command)

        # 증상 신고층. 실로그에서 반려의 절반은 반려어 없이
        # "저장이 안 돼" 같은 증상으로만 온다. 어휘가 매번 달라
        # 유사도 문턱(shared>=2)도 못 넘는다. 다만 텍스트만 보면
        # "안 되는 케이스도 테스트에 넣어줘"까지 걸리므로,
        # **직전 산출물이 다루는 개념과 겹칠 때만** 반려로 친다.
        terms = artifact_terms or _content_words(prior)
        symptom = bool(looks_symptom(command)
                       and (terms & _content_words(command)))

        # 생략형 재시도. 사람은 두 번째부터 짧게 말한다 —
        # "결제 쪽 다시", "재시도 다시 좀". 내용어가 1개만 겹쳐서
        # same_intent의 2개 요구를 못 넘지만, 진행 중인 작업이 있고
        # 재시도 표시가 붙은 짧은 명령은 맥락상 같은 의도로 본다.
        # (텍스트 유사도가 아니라 대화 상태로 판정하는 층이다.)
        cw = _content_words(command)
        elliptical = (
            len(cw) <= 2
            and bool(_RETRY_MARK.search(command))
            and (bool(cw & _content_words(prior)) or bool(_ANAPHORA.search(command)))
        )

        if not (same or explicit or elliptical or symptom):
            self.streak = 0
            self.rung = 0
            self._scope_i = 0
            self._tier = Tier.MID
            self.anchor = command      # 새 의도가 다음 묶음의 앵커가 된다
            return dict(action="proceed", step="new-intent", tier=self._tier,
                        scope=SCOPE_LADDER[self._scope_i], similarity=sim,
                        reason="새로운 의도 — 사다리를 초기화한다.")

        self.streak += 1
        # 앵커는 '내용 있는' 재요청일 때만 갱신한다. 생략형("이거 다시")으로
        # 갱신하면 다음 턴에 비교할 내용어가 사라진다.
        if not elliptical and len(cw) >= 2:
            self.anchor = command

        if self.rung >= self.max_rungs:
            return dict(action="respec", step="exhausted", tier=self._tier,
                        scope="respec", similarity=sim,
                        reason="사다리를 다 썼다. 사람이 스펙을 다시 잡아야 한다.")

        rung = self.ladder[min(self.rung, len(self.ladder) - 1)]
        # 조건부 tier-up: 난이도가 원인인 종류(reasoning)일 때만 모델을 올린다.
        # 축소 사다리에서 tier-up을 상시 칸에서 뺀 대신 여기서 되살린다.
        if (mismatch_kind == "reasoning" and self.ladder is LEAN_LADDER
                and self._tier is not Tier.LARGE and not rung.get("respec")):
            rung = CONDITIONAL_TIER_UP
        self.rung += 1

        # 범위 천장은 "module"이다. SCOPE_LADDER의 마지막 칸 respec은
        # 사다리의 마지막 칸에서만 쓴다 — 중간에 respec 범위로 올라가면
        # 아직 구현을 포기할 단계가 아닌데 구현을 멈추게 된다.
        scope_cap = len(SCOPE_LADDER) - 2          # module
        self._scope_i = min(self._scope_i + rung["scope_up"], scope_cap)
        for _ in range(rung["tier_up"]):
            self._tier = _tier_up(self._tier)

        if rung["reset"] and not rung.get("respec"):
            # 새 세션은 넓혀둔 범위를 물려받지 않는다. 맥락을 버리는 게
            # 리셋의 목적인데 범위만 module로 남으면 입력만 2.4배로
            # 커진 채 같은 실수를 반복한다. 티어는 유지한다 —
            # 난이도 판단은 세션과 무관하게 유효하다.
            self._scope_i = 0

        if rung.get("respec"):
            self._scope_i = len(SCOPE_LADDER) - 1  # respec

        return dict(
            action="respec" if rung.get("respec") else "escalate",
            step=rung["step"], tier=self._tier,
            scope=SCOPE_LADDER[self._scope_i], reset=rung["reset"],
            similarity=sim, explicit=explicit, elliptical=elliptical,
            symptom=symptom, reason=rung["why"],
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
              user_facing: bool = True, carried_tok: int = 0) -> float:
    """B 사다리 한 칸의 비용.

    user_facing=True면 출력 상한을 못 조인다 — 사용자에게 나갈
    완성물이라 "진단 + diff"로 대체할 수 없기 때문이다.

    carried_tok: 이 칸에 도달하기까지 컨텍스트에 눌러앉은 누적 입력.
        리셋 칸에서는 무시된다(누적이 끊기므로). 0이면 종전 계산과 같다.
    """
    tin = int(tok_in * SCOPE_MULT[scope])
    if reset:
        tin += RESET_PRIME_TOK      # 새 세션 — 누적 컨텍스트는 버려진다
    else:
        tin += carried_tok
    out = FIRST_OUT_TOK if user_facing else REWORK_OUT_TOK
    return cost_of(tier, tin, out)


__all__ = ["same_intent", "IntentTracker", "INTENT_LADDER", "LEAN_LADDER",
           "CONDITIONAL_TIER_UP",
           "rung_cost",
           "_content_words"]
