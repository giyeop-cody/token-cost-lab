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
    SessionMemory   동일 설명 반복 감지 → 신규 세션 권고
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

    def to_json(self) -> str:
        return json.dumps({
            "kind": self.kind.value, "tier": self.tier.value,
            "options": self.options, "reason": self.reason,
            "classified_by": self.classified_by,
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
        r"전략|방향|왜 이렇게|장단점", re.I)),
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
             "explain": "3-lines"},
            "결정이 끝난 구현은 중간 모델로 충분. 설명 옵션을 눌러 "
            "출력 토큰을 코드에만 쓴다.", by)

    if kind is Kind.EXPLAIN:
        explicit = bool(re.search(r"자세히|깊게|문서로|튜토리얼|왜 그런지 끝까지", task))
        if explicit:
            return Decision(
                kind, Tier.MID, {"verbosity": "medium", "explain": "full"},
                "명시적으로 상세 설명을 요청한 경우에만 길게 허용.", by)
        return Decision(
            kind, Tier.SMALL, {"verbosity": "low", "explain": "3-lines"},
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


# ── 3. 설명 3줄 강제 ─────────────────────────────────────────
def explain_guard(text: str, max_lines: int = 3) -> str:
    """설명 출력을 상한선으로 자른다. 프롬프트가 무시당해도 여기서 막힌다."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    kept = lines[:max_lines]
    kept.append(f"…(+{len(lines) - max_lines}줄 생략 — 필요하면 '자세히'로 재요청)")
    return "\n".join(kept)


# ── 4. 세션 메모리 — 동일 설명 반복 감지 ──────────────────────
def _norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", s.lower())


@dataclass
class SessionMemory:
    """같은 설명이 반복되면 컨텍스트가 오염된 신호로 보고 리셋을 권고한다.

    반복 설명은 두 배로 손해다. 출력 토큰을 다시 쓰고, 그 출력이 다시
    컨텍스트에 쌓여 이후 모든 턴의 입력 단가를 올린다.
    """
    threshold: int = 2
    turns: int = 0
    seen: dict[str, int] = field(default_factory=dict)
    tokens_in_context: int = 0

    def observe(self, answer: str, tokens: int = 0) -> dict:
        self.turns += 1
        self.tokens_in_context += tokens
        key = hashlib.sha1(_norm(answer)[:400].encode()).hexdigest()[:12]
        self.seen[key] = self.seen.get(key, 0) + 1
        n = self.seen[key]
        if n >= self.threshold:
            return {
                "action": "reset",
                "repeat": n,
                "reason": (f"동일 설명 {n}회 반복 — 컨텍스트에 이미 있는 내용을 "
                           f"다시 생성 중이다. 결론을 파일로 커밋하고 새 세션에서 "
                           f"그 파일만 읽혀라."),
                "carry_over": "specs/*.md + 마지막 결정 사항만",
            }
        return {"action": "continue", "repeat": n}


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
