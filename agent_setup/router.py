# -*- coding: utf-8 -*-
"""작은 모델이 지휘하는 워크플로우 컨트롤러 — 참조 구현.

핵심 아이디어
    비싼 모델을 "기본값"에서 끌어내리고, 값싼 분류기가 매 요청의 종류를
    판정해 필요한 만큼의 모델만 부른다. 분류 비용은 요청당 수십 토큰이라
    한 번이라도 상위 모델 호출을 막으면 즉시 회수된다.

구성
    classify()      작업 종류 판정 (규칙 우선, 애매하면 소형 모델)
    route()         종류 → 티어·옵션 결정
    explain_guard() 설명 3줄 강제
    SessionMemory   컨텍스트 위생 — 반복은 컴팩션, 방향 어긋남만 리셋
    escalate()      실패 시 재시도 → 범위 → 모델 순으로 한 축씩
    estimate()      라우팅 적용 전후 비용 비교

의존성 없음(표준 라이브러리만). LLM 호출부는 주입 가능한 콜러블이라
오프라인에서도 규칙 기반으로 완전히 동작한다.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable


# ── 모델 티어 ────────────────────────────────────────────────
class Tier(str, Enum):
    SMALL = "small"    # 분류·툴호출·추출. $0.15/$0.60 급
    MID = "mid"        # 구현·설명. $1.25/$10 급
    LARGE = "large"    # 설계·난제. $5/$30 급
    EXTERNAL = "web"   # 이미 로그인된 웹 채팅 세션 (정액제)
    BATCH = "batch"    # 비동기 배치 (단가 50%)


# 단가 ($ per 1M tokens) — 발표 시점 리스트가 기준. 각자 값으로 교체할 것.
PRICES: dict[Tier, tuple[float, float]] = {
    Tier.SMALL: (0.15, 0.60),
    Tier.MID: (1.25, 10.00),
    Tier.LARGE: (5.00, 30.00),
    Tier.EXTERNAL: (0.0, 0.0),   # 구독료에 포함 — 종량 과금 없음
    Tier.BATCH: (0.625, 5.00),   # MID의 50%
}


class Kind(str, Enum):
    REASONING = "reasoning"      # 설계·아키텍처·트레이드오프 판단
    IMPLEMENT = "implement"      # 결정된 사항의 코드 작성
    EXPLAIN = "explain"          # 코드·개념 설명
    TOOL = "tool"                # 파일 조작·검색·포맷 변환
    BULK = "bulk"                # 자료조사·정규화 등 대량 비동기


@dataclass
class Decision:
    kind: Kind
    tier: Tier
    options: dict
    reason: str
    classified_by: str = "rule"
    attempt: int = 1              # 몇 번째 시도인가 (1 = 첫 배정)
    scope: str = "unit"           # 이번 시도에서 다시 여는 범위
    reset: bool = False           # 이 시도 전에 세션을 새로 여는가
    step: str = "first"           # first | retry | widen | tier-up | respec
    carry_over: str | None = None  # 리셋 시 이월할 것

    def to_json(self) -> str:
        return json.dumps({
            "kind": self.kind.value, "tier": self.tier.value,
            "options": self.options, "reason": self.reason,
            "classified_by": self.classified_by,
            "attempt": self.attempt, "scope": self.scope,
            "reset": self.reset, "step": self.step,
            "carry_over": self.carry_over,
        }, ensure_ascii=False)


# ── 1. 분류 ──────────────────────────────────────────────────
# 규칙이 먼저다. 규칙으로 잡히면 모델 호출 자체가 0원이다.
# 순서가 곧 우선순위다. 결정적으로 처리 가능한 TOOL을 BULK보다 먼저 본다 —
# "TODO 전부 grep"은 분량 수식어가 붙었을 뿐 여전히 셸 한 줄로 끝나는 일이다.
RULES: list[tuple[Kind, re.Pattern]] = [
    (Kind.TOOL, re.compile(
        r"파일|디렉터리|디렉토리|경로|이름.*바꾸|이동|복사|삭제|"
        r"grep|검색해|찾아줘|포맷|변환|커밋|푸시", re.I)),
    (Kind.BULK, re.compile(
        r"일괄|배치|목록.*조사|정규화|라벨링|임베딩|크롤|수집|"
        r"(전부|모두)\s*(조사|수집|번역|요약|분류|정리)|"
        r"\d{2,}\s*(개|건|행|페이지)", re.I)),
    (Kind.REASONING, re.compile(
        r"설계|아키텍처|구조.*정해|트레이드오프|어떤 방식이|비교.*결정|"
        r"전략|방향|장단점|"
        r"왜\s*이(렇게|_?구조|\s*\S{0,12}\s*이렇게)|"
        r"근본\s*원인|원인(을|\s)*(분석|파악)|"
        r"어떤\s*방식으로|무엇이\s*나은", re.I)),
    (Kind.EXPLAIN, re.compile(
        r"설명|무슨 뜻|어떻게 동작|why|이해가|알려줘.*의미", re.I)),
    (Kind.IMPLEMENT, re.compile(
        r"구현|만들어|작성해|추가해|고쳐|수정해|리팩터|버그|테스트.*작성", re.I)),
]

CLASSIFY_PROMPT = (
    "Classify the request into exactly one label: "
    "reasoning, implement, explain, tool, bulk. Answer with the label only.\n\n"
)


def classify(task: str, small_llm: Callable[[str], str] | None = None) -> tuple[Kind, str]:
    """작업 종류를 판정한다. 규칙 우선, 실패 시에만 소형 모델.

    반환: (종류, 판정 주체)
    """
    for kind, pat in RULES:
        if pat.search(task):
            return kind, "rule"
    if small_llm is None:
        return Kind.IMPLEMENT, "default"
    raw = small_llm(CLASSIFY_PROMPT + task).strip().lower()
    for kind in Kind:
        if kind.value in raw:
            return kind, "small-llm"
    return Kind.IMPLEMENT, "default"


# ── 2. 라우팅 ────────────────────────────────────────────────
def route(task: str,
          small_llm: Callable[[str], str] | None = None,
          *,
          allow_external: bool = True,
          allow_batch: bool = True,
          deadline_sensitive: bool = False) -> Decision:
    """작업 → 실행 티어와 옵션."""
    kind, by = classify(task, small_llm)

    if kind is Kind.REASONING:
        if allow_external:
            return Decision(
                kind, Tier.EXTERNAL,
                {"mode": "web-chat", "handoff": "spec.md"},
                "긴 추론은 정액제 웹 세션에서 끝내고 결론(스펙)만 주입한다. "
                "종량 과금되는 추론 토큰을 0으로 만든다.", by)
        return Decision(
            kind, Tier.LARGE,
            {"reasoning_effort": "medium", "verbosity": "low"},
            "웹 경로 불가 → 상위 모델. 단 effort는 medium 이하로 제한.", by)

    if kind is Kind.IMPLEMENT:
        return Decision(
            kind, Tier.MID,
            {"reasoning_effort": "low", "verbosity": "low",
             "explain": "3-lines", "max_out_tok": FIRST_OUT_TOK},
            "결정이 끝난 구현은 중간 모델로 충분. 설명 옵션을 눌러 "
            "출력 토큰을 코드에만 쓴다.", by)

    if kind is Kind.EXPLAIN:
        explicit = bool(re.search(r"자세히|깊게|문서로|튜토리얼|왜 그런지 끝까지", task))
        if explicit:
            return Decision(
                kind, Tier.MID, {"verbosity": "medium", "explain": "full"},
                "명시적으로 상세 설명을 요청한 경우에만 길게 허용.", by)
        return Decision(
            kind, Tier.SMALL, {"verbosity": "low", "explain": "3-lines",
                               "max_out_tok": EXPLAIN_OUT_TOK},
            "구현 직후의 관성적 설명 → 3줄로 상한. 코드를 읽으면 아는 내용은 "
            "재생산하지 않는다.", by)

    if kind is Kind.TOOL:
        return Decision(
            kind, Tier.SMALL,
            {"prefer": "code-execution", "verbosity": "low"},
            "툴 조작은 소형 모델. 가능하면 LLM 없이 결정적 코드로 처리.", by)

    # BULK
    if allow_batch and not deadline_sensitive:
        return Decision(
            kind, Tier.BATCH,
            {"window": "24h", "fallback": "sync-after-2h"},
            "사람이 기다리지 않는 대량 작업 → 배치로 단가 50%. "
            "지연에 대비해 폴백 시각을 정해둔다.", by)
    return Decision(
        kind, Tier.MID, {"verbosity": "low"},
        "마감이 걸려 있어 배치 부적합 → 동기 처리.", by)


# ── 2-b. 리워크 에스컬레이션 ─────────────────────────────────
# 라우팅은 "첫 배정"만 정한다. 그러나 비용을 실제로 태우는 것은 실패 후
# 같은 일을 다시 시키는 구간이다(exp09-C: 48턴 리워크 = 16.6배).
#
# 두 가지를 구분한다.
#   실패(test-fail) — 방향은 맞는데 결과가 틀렸다. 리워크로 푼다.
#   어긋남(misalign) — 완료했는데 원하던 방향이 아니다. 리셋으로 푼다.
#
# 실패에 대한 원칙: 한 번에 다 올리지 않는다.
#   실패의 상당수는 사소한 누락(임포트·엣지케이스)이라 제자리 재시도로 끝난다.
#   첫 실패부터 범위와 모델을 동시에 올리면, 싸게 끝났을 일을 비싸게 만든다.
#   그래서 사다리를 잘게 나눈다: 재시도 → 범위 → 모델 → 중단.
#   축을 하나씩만 움직이므로 어느 축이 문제였는지도 드러난다.

SCOPE_LADDER = ["unit", "file", "module", "respec"]
SCOPE_LABEL = {
    "unit": "실패한 함수/블록만",
    "file": "파일 전체 + 호출부",
    "module": "모듈 + 인접 계약(인터페이스·스키마)",
    "respec": "구현 중단 — 스펙으로 되돌아감",
}

TIER_LADDER = [Tier.SMALL, Tier.MID, Tier.LARGE]

# 첫 배정에도 출력 예산을 준다. 상한이 이 설계의 가장 큰 레버인데
# 첫 턴만 무제한이면 정작 제일 긴 출력이 그대로 나간다.
# 2500은 "구현 한 덩어리 + 3줄 설명"의 실측 상한이다.
FIRST_OUT_TOK = 2500
EXPLAIN_OUT_TOK = 500         # 3줄 설명에 2500을 열어둘 이유가 없다

# 리워크 턴의 비용은 81~92%가 출력이다(MID 출력 단가가 입력의 8배).
# 그래서 사다리를 싸게 만드는 레버는 티어가 아니라 **출력량**이다.
#
# 실패를 고치는 턴은 파일을 다시 쓸 이유가 없다. 필요한 것은
# "왜 깨졌는가" 몇 줄과 최소 패치뿐이다. 전문 재작성을 막으면
# 상한 비용이 45% 내려간다. 상한 탓에 성공률이 20%p 떨어져도
# 여전히 무제한보다 싸다 — 출력 단가가 그만큼 지배적이다.
REWORK_OUT_TOK = 900          # 진단 + 통합 diff에 필요한 실측 여유분
REWORK_PATCH_ONLY = "unified-diff"

# 리셋은 공짜가 아니다. 새 세션은 이월 문서를 다시 읽혀야 하고,
# 그 재장전 입력이 비용이다. 그래서 리셋을 사다리 매 칸에 넣지 않는다.
RESET_PRIME_TOK = 600

# 한 칸에 축 하나씩. attempt 2부터 순서대로 적용된다.
REWORK_LADDER = [
    dict(step="retry", scope_up=0, tier_up=0, reset=False,
         opts={"attach": "failing-test + diff", "explain": "diagnosis-first",
               "output": REWORK_PATCH_ONLY, "max_out_tok": REWORK_OUT_TOK},
         why="같은 범위·같은 모델로 한 번 더. 실패의 상당수는 사소한 누락이라 "
             "여기서 끝난다. 추가 비용이 거의 없는 칸을 먼저 쓴다."),
    dict(step="widen", scope_up=1, tier_up=0, reset=True,
         opts={"attach": "failing-test + diff + 호출부",
               "output": REWORK_PATCH_ONLY, "max_out_tok": REWORK_OUT_TOK},
         why="모델은 그대로 두고 보는 범위만 넓힌다. 두 번째 실패는 "
             "모델이 약해서가 아니라 범위가 잘못 잘린 경우가 많다."),
    dict(step="tier-up", scope_up=0, tier_up=1, reset=True,
         opts={"require": "write-test-first",
               "output": "diagnosis-then-patch", "max_out_tok": 400,
               "apply_with": Tier.MID.value},
         why="범위를 넓혀도 안 되면 그때 모델을 올린다. 단 상위 모델에게는 "
             "진단만 400토큰으로 받고 적용은 중간 모델이 한다 — 비싼 티어의 "
             "출력을 길게 받는 것이 이 칸의 유일한 비용 폭탄이다."),
]


def _tier_up(tier: Tier) -> Tier:
    """한 단계 상위 티어. 사다리 밖(EXTERNAL/BATCH)이면 MID에서 시작."""
    if tier not in TIER_LADDER:
        return Tier.MID
    i = TIER_LADDER.index(tier)
    return TIER_LADDER[min(i + 1, len(TIER_LADDER) - 1)]


def escalate(prev: Decision,
             *,
             failure: str = "test-fail",
             attempt: int | None = None,
             allow_external: bool = True,
             max_attempts: int = 5) -> Decision:
    """실패한 시도 → 다음 시도의 범위·티어·리셋 여부.

    한 칸에 축 하나씩만 올린다.

    attempt 2: 제자리 재시도 (범위·모델 그대로, 실패 증거 첨부) — 리셋 없음
    attempt 3: 범위 확대 (모델 그대로) — 리셋
    attempt 4: 티어 상승 (범위 그대로) — 리셋
    attempt 5: 중단. 구현을 더 시키지 않고 스펙 재작성으로 되돌린다.
    """
    n = attempt if attempt is not None else prev.attempt + 1

    if n >= max_attempts:
        tier = Tier.EXTERNAL if allow_external else Tier.LARGE
        return Decision(
            Kind.REASONING, tier,
            {"mode": "web-chat" if tier is Tier.EXTERNAL else "reasoning",
             "handoff": "failures.md + 현재 코드", "output": "spec.md"},
            f"{n}회차 — 재시도·범위·모델을 다 써도 안 되면 스펙 문제다. "
            f"구현을 멈추고 실패 기록을 들고 설계로 되돌아간다. "
            f"여기서 모델을 더 올리면 비용만 오른다.",
            prev.classified_by, attempt=n, scope="respec",
            reset=True, step="respec",
            carry_over="specs/*.md + failures.md + 마지막 결정 사항")

    rung = REWORK_LADDER[min(n - 2, len(REWORK_LADDER) - 1)]

    si = SCOPE_LADDER.index(prev.scope) if prev.scope in SCOPE_LADDER else 0
    scope = SCOPE_LADDER[min(si + rung["scope_up"], len(SCOPE_LADDER) - 2)]
    if rung["tier_up"]:
        tier = _tier_up(prev.tier)
    else:
        tier = prev.tier if prev.tier in TIER_LADDER else Tier.MID

    opts = dict(prev.options)
    opts["scope"] = scope
    opts["verbosity"] = "low"
    opts["explain"] = "diagnosis-first"
    opts.update(rung["opts"])
    if failure != "test-fail":
        opts["attach"] = failure

    moved = ("범위 " + SCOPE_LABEL[scope] if rung["scope_up"]
             else "티어 " + prev.tier.value + "→" + tier.value if rung["tier_up"]
             else "그대로 (증거만 추가)")

    return Decision(
        prev.kind, tier, opts,
        f"{n}회차 [{rung['step']}] {moved} — {rung['why']}",
        prev.classified_by, attempt=n, scope=scope,
        reset=rung["reset"], step=rung["step"],
        carry_over=("specs/*.md + failing test + 지금까지의 결정"
                    if rung["reset"] else None))


@dataclass
class ReworkTracker:
    """작업별 시도 횟수를 들고 다음 배정을 내주는 얇은 상태 기계.

    측정 대상은 비용만이 아니라 **턴 수**다. 같은 task_id가 몇 번
    돌아왔는지가 곧 설계 품질 지표다.
    """
    max_attempts: int = 5
    attempts: dict[str, int] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)

    def first(self, task_id: str, task: str, **kw) -> Decision:
        self.attempts[task_id] = 1
        d = route(task, **kw)
        self.history.append({"id": task_id, "attempt": 1, "step": "first",
                             "tier": d.tier.value, "scope": d.scope,
                             "reset": False})
        return d

    def again(self, task_id: str, prev: Decision,
              failure: str = "test-fail", **kw) -> Decision:
        n = self.attempts.get(task_id, 1) + 1
        self.attempts[task_id] = n
        d = escalate(prev, failure=failure, attempt=n,
                     max_attempts=self.max_attempts, **kw)
        self.history.append({"id": task_id, "attempt": n, "step": d.step,
                             "tier": d.tier.value, "scope": d.scope,
                             "reset": d.reset})
        return d

    def rework_turns(self) -> int:
        """첫 배정을 제외한 재시도 턴의 총합."""
        return sum(max(0, n - 1) for n in self.attempts.values())

    def resets(self) -> int:
        return sum(1 for h in self.history if h["reset"])

    def report(self) -> str:
        if not self.attempts:
            return "기록 없음"
        worst = max(self.attempts.items(), key=lambda kv: kv[1])
        return (f"작업 {len(self.attempts)}건 · 재시도 {self.rework_turns()}턴 · "
                f"리셋 {self.resets()}회 · 최다 리워크 '{worst[0]}' {worst[1]}회")


# ── 3. 설명 3줄 강제 ─────────────────────────────────────────
def explain_guard(text: str, max_lines: int = 3) -> str:
    """설명 출력을 상한선으로 자른다. 프롬프트가 무시당해도 여기서 막힌다."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    kept = lines[:max_lines]
    kept.append(f"…(+{len(lines) - max_lines}줄 생략 — 필요하면 '자세히'로 재요청)")
    return "\n".join(kept)


# ── 4. 세션 위생 — 리셋은 마지막 수단 ────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", s.lower())


# "완료했는데 원하던 방향이 아니다"의 신호. 실패(test-fail)와는 다른 종류다.
_REJECT_PAT = re.compile(
    r"(그게\s*아니|이게\s*아니|원하는\s*(게|것)\s*아니"
    # 명사구 + '말고'. 실로그에서 가장 흔한 반려 형태인데
    # 대명사(이거/그거)만 받으면 "복잡한 거 말고"를 통째로 놓친다.
    r"|\S*\s*(거|건|것|걸|쪽|방식|스타일)\s*말고"
    r"|(이거|그거|이건|그건|이렇게|그렇게)\s*말고"
    r"|말고\s*(아까|이전|원래|처음|기존)"
    r"|의도(와|가)\s*다르|방향이\s*(다르|틀)|되돌려|롤백"
    # '처음부터 심플하게 다시'처럼 부사가 끼어드는 실제 어순을 허용한다.
    r"|다시\s*해|처음부터(\s*\S+){0,2}\s*다시|아까\s*(방식|것|거)"
    r"|왜\s*이렇게|엎[고어]|갈아\s*엎)")


# 증상 신고. "저장이 안 돼", "클릭해도 안 열려" — 실로그 반려의 절반이
# 이 형태인데 반려어가 하나도 없다. 다만 이 패턴 **단독으로는 쓰면 안 된다**:
# "안 되는 케이스도 테스트에 넣어줘" 같은 신규 지시가 전부 걸려
# 거짓양성이 5/6까지 올라간다. 반드시 아래 두 조건과 함께 쓴다.
_SYMPTOM_PAT = re.compile(
    r"(안\s*(되|돼|열려|먹|나와|보여|바뀌|저장|동작)"
    r"|사라져|사라졌|날아갔|초기화돼"
    r"|에러\s*(가|난|나|떠)|오류\s*(가|난|나)|깨져|깨졌|멈춰|먹통"
    r"|(는|은|이|가)\s*되는데)")

# 신규 작업 지시의 어미. 이걸로 끝나면 '앞으로 만들 것'에 대한
# 요구사항 서술이지 이미 만든 것에 대한 반려가 아니다.
_REQUEST_TAIL = re.compile(
    r"(해줘|해라|하자|넣어줘|추가(해|하)|만들어|바꿔줘|피해줘|줘요?|주세요"
    r"|하면\s*좋겠|했으면)\s*[.!?]*\s*$")


def looks_symptom(text: str) -> bool:
    """증상 신고인가. 요청 어미로 끝나면 신규 지시로 본다."""
    t = text or ""
    return bool(_SYMPTOM_PAT.search(t)) and not _REQUEST_TAIL.search(t)


def looks_rejected(text: str) -> bool:
    return bool(_REJECT_PAT.search(text or ""))


@dataclass
class SessionMemory:
    """컨텍스트 위생. **리셋은 마지막 수단이다.**

    리셋을 반복 감지만으로 걸면 안 된다. 새 세션은 맥락이 부서지고,
    이월 문서를 다시 읽히는 재장전 비용이 든다. 같은 말을 두 번 했다는
    이유로 세션을 버리면 아직 쓸모 있는 문맥까지 같이 버린다.

    그래서 세 단계로 나눈다.
        continue → compact → reset

    compact  같은 설명이 쌓이거나 컨텍스트가 비대해졌을 때. 스레드는 유지하고
             결론만 남긴다. 되돌릴 수 있는 조치다.
    reset    **완료된 작업이 원하던 방향이 아닐 때**만. 이때는 잘못된 목표가
             이미 컨텍스트에 굳어 있어서, 같은 스레드에서 고치면 모델이
             계속 그 목표로 되돌아간다. 이 경우에만 버리는 편이 싸다.
    """
    repeat_threshold: int = 3        # 반복 → 컴팩션 (리셋 아님)
    bloat_tokens: int = 60_000       # 컨텍스트 비대 → 컴팩션
    turns: int = 0
    seen: dict[str, int] = field(default_factory=dict)
    tokens_in_context: int = 0
    compactions: int = 0
    resets: int = 0

    # ── 진행 중 관찰: 여기서는 절대 리셋하지 않는다 ──
    def observe(self, answer: str, tokens: int = 0) -> dict:
        self.turns += 1
        self.tokens_in_context += tokens
        key = hashlib.sha1(_norm(answer)[:400].encode()).hexdigest()[:12]
        self.seen[key] = self.seen.get(key, 0) + 1
        n = self.seen[key]

        if n >= self.repeat_threshold:
            self.compactions += 1
            return {
                "action": "compact", "repeat": n,
                "reason": (f"동일 설명 {n}회 — 컨텍스트에 이미 있는 내용을 "
                           f"다시 생성 중이다. 세션은 유지하고 결론만 남긴다."),
                "keep": "마지막 결정 사항 + 열려 있는 TODO",
                "drop": "중복 설명·중간 산출물",
            }
        if self.tokens_in_context >= self.bloat_tokens:
            self.compactions += 1
            return {
                "action": "compact", "repeat": n,
                "reason": (f"컨텍스트 {self.tokens_in_context:,}토큰 — 이후 모든 "
                           f"턴의 입력 단가가 여기에 비례한다."),
                "keep": "마지막 결정 사항 + 열려 있는 TODO",
                "drop": "중복 설명·중간 산출물",
            }
        return {"action": "continue", "repeat": n}

    # ── 완료 시점 판정: 리셋은 여기서만 나온다 ──
    def review(self, *, done: bool = True,
               ac_passed: bool | None = None,
               user_verdict: str | None = None) -> dict:
        """끝난 작업의 방향을 본다.

        ac_passed=False      결함이다. 방향은 맞다 → 리워크 사다리로.
        user_verdict 가 거부 완료했는데 원하던 방향이 아니다 → 리셋.
        """
        if not done:
            return {"action": "continue", "reason": "아직 완료 전 — 판정 대상 아님"}

        rejected = (user_verdict == "reject"
                    or looks_rejected(user_verdict or ""))

        if rejected:
            self.resets += 1
            return {
                "action": "reset",
                "signal": "misaligned",
                "reason": ("완료된 결과가 원하던 방향이 아니다. 잘못된 목표가 "
                           "이미 컨텍스트에 굳어 있어, 같은 세션에서 고치면 "
                           "모델이 계속 그 목표로 되돌아간다."),
                "carry_over": ("specs/*.md + 무엇이 왜 아니었는지 1줄 + "
                               "유지할 결정 사항"),
                "drop": "이번 방향으로 만든 코드·설명 전부",
            }

        if ac_passed is False:
            return {
                "action": "rework",
                "signal": "test-fail",
                "reason": ("검증 실패는 방향 문제가 아니라 결함이다. "
                           "세션을 버리지 말고 리워크 사다리를 한 칸 올린다."),
            }

        return {"action": "continue", "signal": "ok",
                "reason": "통과 — 결론을 파일로 커밋해두면 다음 세션이 싸진다."}


# ── 5. 비용 추정 ─────────────────────────────────────────────
def cost_of(tier: Tier, tok_in: int, tok_out: int) -> float:
    pin, pout = PRICES[tier]
    return tok_in * pin / 1e6 + tok_out * pout / 1e6


def estimate(workload: Iterable[tuple[str, int, int]],
             baseline: Tier = Tier.LARGE,
             **route_kw) -> dict:
    """워크로드에 라우팅을 적용했을 때의 절감 추정.

    workload: (작업설명, 입력토큰, 출력토큰) 목록
    """
    rows, base_total, routed_total = [], 0.0, 0.0
    for task, ti, to in workload:
        d = route(task, **route_kw)
        b = cost_of(baseline, ti, to)
        # 설명 3줄 강제는 출력 토큰을 실제로 줄인다(보수적으로 60%만 반영)
        to_eff = int(to * 0.4) if d.options.get("explain") == "3-lines" else to
        r = cost_of(d.tier, ti, to_eff)
        base_total += b
        routed_total += r
        rows.append({"task": task[:38], "kind": d.kind.value,
                     "tier": d.tier.value, "base": b, "routed": r})
    saved = (base_total - routed_total) / base_total * 100 if base_total else 0.0
    return {"rows": rows, "baseline_usd": base_total,
            "routed_usd": routed_total, "saved_pct": saved}


def rework_cost(task: str, tok_in: int, tok_out: int,
                fails: int, *, strategy: str = "escalate",
                **route_kw) -> dict:
    """실패가 fails회 났을 때 총비용. 두 전략을 비교한다.

    strategy="retry"    : 같은 범위·같은 모델로 계속 재시도 (흔한 기본값)
    strategy="escalate" : 사다리대로 재시도 → 범위 → 모델 순으로 한 축씩 (권장)
    strategy="topfirst" : 처음부터 최상위 모델 (비싸지만 실패가 적다는 가정)

    리셋이 걸린 칸에는 재장전 입력(RESET_PRIME_TOK)을 더한다. 새 세션은
    이월 문서를 다시 읽혀야 하므로 공짜가 아니다 — 이 비용을 빼고 계산하면
    사다리가 실제보다 싸 보인다.
    """
    d = route(task, **route_kw)
    total, turns, trail = 0.0, 0, []

    if strategy == "topfirst":
        d = Decision(d.kind, Tier.LARGE, dict(d.options), "최상위 고정",
                     d.classified_by)

    resets = 0
    for i in range(fails + 1):
        # 재시도는 범위가 넓어질수록 입력이 커진다(파일→모듈).
        mult = {"unit": 1.0, "file": 1.6, "module": 2.4, "respec": 1.2}[d.scope]
        tin = int(tok_in * mult)
        if d.reset:                      # 새 세션 = 이월 문서 재장전
            tin += RESET_PRIME_TOK
            resets += 1
        # 리워크 턴은 파일을 다시 쓰지 않는다 — 진단 + 패치만 받는다.
        # 비용의 8할이 출력이라 이 상한이 사다리의 가장 큰 레버다.
        tout = min(tok_out, d.options.get("max_out_tok", tok_out))
        c = cost_of(d.tier, tin, tout)
        # 상위 티어는 진단만 내고 적용은 한 단계 아래가 한다.
        applier = d.options.get("apply_with")
        if applier:
            c += cost_of(Tier(applier), tin, tok_out)
        total += c
        turns += 1
        trail.append({"attempt": d.attempt, "step": d.step,
                      "tier": d.tier.value, "scope": d.scope,
                      "reset": d.reset, "out_tok": tout, "usd": c})
        if i == fails:
            break
        if strategy == "escalate":
            d = escalate(d)
        else:
            d = Decision(d.kind, d.tier, d.options, d.reason,
                         d.classified_by, attempt=d.attempt + 1, scope=d.scope)

    return {"strategy": strategy, "turns": turns, "resets": resets,
            "usd": total, "trail": trail}


def breakeven(task: str, tok_in: int, tok_out: int,
              esc_fails: int = 2, max_retry: int = 40,
              **route_kw) -> dict:
    """에스컬레이션은 턴당 더 비싸다. 언제 이득이 되는가?

    정직한 비교는 "같은 실패 횟수"가 아니다 — 에스컬레이션의 값어치는
    루프를 **더 빨리 끝내는 것**에 있다. 그래서 묻는다:
    사다리를 타고 esc_fails회 만에 끝낸 비용을, 같은 자리에서 반복하는
    전략이 몇 턴째에 따라잡는가.
    """
    esc = rework_cost(task, tok_in, tok_out, fails=esc_fails,
                      strategy="escalate", **route_kw)
    for n in range(1, max_retry + 1):
        r = rework_cost(task, tok_in, tok_out, fails=n,
                        strategy="retry", **route_kw)
        if r["usd"] >= esc["usd"]:
            return {"escalate_turns": esc["turns"], "escalate_usd": esc["usd"],
                    "breakeven_retry_turns": r["turns"],
                    "breakeven_usd": r["usd"]}
    return {"escalate_turns": esc["turns"], "escalate_usd": esc["usd"],
            "breakeven_retry_turns": None, "breakeven_usd": None}


if __name__ == "__main__":
    demo = [
        ("결제 모듈 아키텍처를 어떤 방식으로 갈지 트레이드오프 정리해줘", 1200, 3000),
        ("정해진 스펙대로 결제 핸들러 구현해줘", 1800, 2500),
        ("방금 짠 코드 설명해줘", 900, 800),
        ("src 밑에서 TODO 전부 grep 해줘", 400, 300),
        ("경쟁사 40개 가격 페이지 조사해서 정규화해줘", 5000, 8000),
    ]
    print("=" * 78)
    for task, ti, to in demo:
        d = route(task)
        print(f"[{d.kind.value:9s}] → {d.tier.value:8s} {d.options}")
        print(f"            {d.reason}")
    print("=" * 78)
    r = estimate(demo)
    for row in r["rows"]:
        print(f"  {row['task']:<40s} {row['tier']:<8s} "
              f"${row['base']:.4f} → ${row['routed']:.4f}")
    print(f"\n  전부 LARGE: ${r['baseline_usd']:.4f}")
    print(f"  라우팅 적용: ${r['routed_usd']:.4f}   절감 {r['saved_pct']:.1f}%")

    # ── 리워크: 한 칸에 축 하나씩 ──
    print("\n" + "=" * 78)
    print("리워크 사다리 — '정해진 스펙대로 결제 핸들러 구현해줘'가 계속 실패")
    print("=" * 78)
    t = ReworkTracker()
    d = t.first("pay-handler", "정해진 스펙대로 결제 핸들러 구현해줘")
    print(f"  1회차 [first   ] {d.tier.value:6s} scope={d.scope:7s} "
          f"reset=  -   {SCOPE_LABEL[d.scope]}")
    for i in range(4):
        d = t.again("pay-handler", d)
        print(f"  {d.attempt}회차 [{d.step:8s}] {d.tier.value:6s} "
              f"scope={d.scope:7s} reset={'예' if d.reset else ' - '}  "
              f"{SCOPE_LABEL[d.scope]}")
        print(f"         └ {d.reason}")
    print(f"\n  {t.report()}")
    print("  세션 리셋은 2회차에 없다 — 짧은 리워크는 맥락을 그대로 들고 간다.")

    # ── 세션: 반복은 컴팩션, 어긋남만 리셋 ──
    print("\n" + "=" * 78)
    print("세션 위생 — 리셋은 마지막 수단")
    print("=" * 78)
    m = SessionMemory()
    for i in range(3):
        r = m.observe("이 함수는 사용자 입력을 검증합니다.", 400)
        print(f"  반복 {r['repeat']}회 → {r['action']}")
    print("  ↑ 같은 말을 반복해도 세션은 살아 있다. 결론만 압축한다.")
    rv = m.review(done=True, ac_passed=False)
    print(f"  완료·검증실패        → {rv['action']}  ({rv['signal']})")
    rv = m.review(done=True, ac_passed=True,
                  user_verdict="이게 아니라 반대 방향인데요")
    print(f"  완료·방향 어긋남     → {rv['action']}  ({rv['signal']})")
    print(f"     이월: {rv['carry_over']}")

    print("\n  [짧은 리워크] 1회 실패로 끝나면 사다리는 손해가 없다:")
    for f in (0, 1):
        a = rework_cost("정해진 스펙대로 결제 핸들러 구현해줘", 1800, 2500,
                        fails=f, strategy="retry")
        b = rework_cost("정해진 스펙대로 결제 핸들러 구현해줘", 1800, 2500,
                        fails=f, strategy="escalate")
        print(f"    실패 {f}회  제자리 ${a['usd']:.4f}  사다리 ${b['usd']:.4f}"
              f"  (리셋 {b['resets']}회)")

    print("\n  [정직한 비교] 길어지면 사다리가 턴당 더 비싸다:")
    for st in ("retry", "escalate", "topfirst"):
        rc = rework_cost("정해진 스펙대로 결제 핸들러 구현해줘",
                         1800, 2500, fails=3, strategy=st)
        print(f"    {st:9s} {rc['turns']}턴  ${rc['usd']:.4f}")
    print("    → 같은 턴 수라면 제자리 재시도가 싸다. 당연하다.")

    be = breakeven("정해진 스펙대로 결제 핸들러 구현해줘", 1800, 2500,
                   esc_fails=2)
    print("\n  [그래서 진짜 질문] 범위를 넓혀 빨리 끝내면 언제 이득인가:")
    print(f"    에스컬레이션 {be['escalate_turns']}턴에 종료  "
          f"${be['escalate_usd']:.4f}")
    print(f"    제자리 재시도는 {be['breakeven_retry_turns']}턴째에 "
          f"${be['breakeven_usd']:.4f}로 추월")
    print(f"    → 제자리 재시도가 {be['breakeven_retry_turns']}턴 안에 "
          f"끝난다면 그게 낫다.")
    print("      그보다 오래 끌 것 같으면 범위를 넓히는 쪽이 싸다.")
    print("      exp09-C의 48턴 리워크(16.6배)는 이 분기점을 한참 넘긴 사례다.")
