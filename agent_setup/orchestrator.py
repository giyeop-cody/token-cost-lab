# -*- coding: utf-8 -*-
"""사다리 A와 B를 하나의 상태 기계로 묶는다.

두 사다리는 **다른 시간축**에서 돈다. 그래서 '합친다'는 것은
칸을 이어 붙이는 게 아니라, 서로의 상태를 물려주는 것이다.

    ┌─ 사용자 턴 ─────────────────────────────────────────┐
    │  B: 이 명령이 직전 의도의 반복인가?                  │
    │      ├ 새 의도  → A를 초기화하고 첫 배정             │
    │      ├ 반복     → B 사다리 한 칸 (A의 티어를 물려받음)│
    │      └ 소진     → respec, 사람에게 넘김              │
    │                                                      │
    │  ┌─ 턴 내부(사용자는 안 봄) ───────────────────────┐ │
    │  │  A: 테스트/AC 실패 → 사다리 한 칸 → 재실행      │ │
    │  │     AC 통과할 때까지, 또는 max_attempts까지     │ │
    │  └─────────────────────────────────────────────────┘ │
    │  결과물 사용자에게 전달                              │
    └──────────────────────────────────────────────────────┘

핵심 규칙 세 가지 —

**① B는 A가 도달한 티어 아래로 내려가지 않는다.**
   A가 이미 LARGE까지 올라가서 AC를 통과시킨 결과물을 사용자가 반려했다면,
   B가 MID부터 다시 시작하는 건 명백한 퇴보다. 이미 알아낸 난이도 정보를
   버리는 것이기 때문이다. `tier_floor`로 막는다.

**② B가 도는 순간 A의 실패 카운트는 초기화된다.**
   B가 돈다는 건 A가 "성공했다"고 잘못 판정하고 빠져나왔다는 뜻이다.
   새 범위·새 티어로 다시 배정하므로 A는 그 조건에서 처음부터 센다.

**③ 새 의도가 오면 둘 다 초기화된다.**
   앞 작업의 난이도를 다음 작업에 물려주면 안 된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from router import (
    Decision, Tier, ReworkTracker, SessionMemory, SCOPE_LADDER,
    route, escalate, cost_of, FIRST_OUT_TOK, REWORK_OUT_TOK,
    RESET_PRIME_TOK,
)
from ladder_b import IntentTracker, rung_cost
from intent_guard import classify_mismatch

_TIER_RANK = {Tier.SMALL: 0, Tier.MID: 1, Tier.LARGE: 2}


def _max_tier(a: Tier, b: Tier) -> Tier:
    """두 티어 중 높은 쪽. B가 A보다 낮게 내려가는 것을 막는 데 쓴다."""
    if a is Tier.EXTERNAL:
        return b
    if b is Tier.EXTERNAL:
        return a
    return a if _TIER_RANK.get(a, 0) >= _TIER_RANK.get(b, 0) else b


@dataclass
class TaskState:
    """작업 하나에 대해 A와 B가 공유하는 상태."""
    task_id: str
    tier_floor: Tier = Tier.SMALL     # A가 도달한 최고 티어 — B의 하한
    last: Decision | None = None
    inner_attempts: int = 0           # 이번 턴에서 A가 돈 횟수
    turns: int = 0                    # 사용자 턴을 몇 번 태웠나
    cost: float = 0.0
    trace: list[dict] = field(default_factory=list)


@dataclass
class Orchestrator:
    """A + B 결합 실행기.

    사용법은 두 개의 진입점뿐이다 —
      `user_turn(task_id, command)` : 사용자 명령이 올 때마다
      `inner(task_id, ac_passed)`   : 턴 내부에서 검증 결과가 나올 때마다
    """
    tok_in: int = 1_800
    max_inner: int = 5
    rework: ReworkTracker = field(default_factory=ReworkTracker)
    intent: IntentTracker = field(default_factory=IntentTracker)
    memory: SessionMemory = field(default_factory=SessionMemory)
    tasks: dict[str, TaskState] = field(default_factory=dict)

    # ── 사용자 턴 ────────────────────────────────────────────
    def user_turn(self, task_id: str, command: str,
                  *, mismatch_kind: str | None = None) -> dict:
        st = self.tasks.setdefault(task_id, TaskState(task_id))
        st.turns += 1
        st.inner_attempts = 0

        # 반려 사유를 분류해 조건부 tier-up의 트리거로 쓴다.
        # 명시적으로 mismatch_kind를 받으면 그걸 쓰고, 아니면
        # 사용자 발화 자체를 classify_mismatch로 판정한다.
        # (의도불일치 5종 중 'reasoning'일 때만 모델을 올린다 —
        #  다른 4종은 티어를 올려도 안 고쳐지므로 낭비다.)
        if mismatch_kind is None:
            mismatch_kind, _ = classify_mismatch(command)
        obs = self.intent.observe(command, mismatch_kind=mismatch_kind)
        action, step = obs["action"], obs["step"]

        # 사람에게 넘길 단계 — 더 좋은 모델로도 안 풀린다.
        if action == "respec":
            st.trace.append(dict(layer="B", step="respec", cost=0.0))
            return dict(layer="B", action="respec", tier=None, scope="respec",
                        cost=0.0, reason=obs["reason"], task=st)

        # 새 의도 → 둘 다 초기화하고 첫 배정.
        if step in ("first", "new-intent"):
            st.tier_floor = Tier.SMALL
            d = self.rework.first(task_id, command)
            st.last = d
            st.tier_floor = _max_tier(st.tier_floor, d.tier)
            c = cost_of(d.tier, self.tok_in, FIRST_OUT_TOK)
            st.cost += c
            st.trace.append(dict(layer="A", step="first", tier=d.tier.value,
                                 scope=d.scope, cost=c))
            return dict(layer="A", action="proceed", tier=d.tier,
                        scope=d.scope, cost=c, reason="첫 배정", task=st)

        # 반복 → B 사다리 한 칸. 여기서 A의 티어를 물려받는다.
        tier = _max_tier(obs["tier"], st.tier_floor)
        scope = obs["scope"]
        reset = obs.get("reset", False)
        c = rung_cost(tier, self.tok_in, reset=reset, scope=scope)
        st.cost += c
        st.tier_floor = _max_tier(st.tier_floor, tier)
        # B가 새 조건을 깔았으므로 A는 그 조건에서 처음부터 센다.
        self.rework.attempts[task_id] = 1
        if st.last is not None:
            # B가 깐 새 조건을 A가 이어받을 수 있도록 Decision을 갱신한다.
            st.last = Decision(
                kind=st.last.kind, tier=tier, options=dict(st.last.options),
                reason=obs["reason"], classified_by=st.last.classified_by,
                attempt=1, scope=scope, reset=reset, step=step)
        st.trace.append(dict(layer="B", step=step, tier=tier.value,
                             scope=scope, reset=reset, cost=c))
        return dict(layer="B", action="escalate", tier=tier, scope=scope,
                    reset=reset, cost=c, reason=obs["reason"],
                    similarity=obs.get("similarity"), task=st)

    # ── 턴 내부 ──────────────────────────────────────────────
    def inner(self, task_id: str, ac_passed: bool,
              failure: str = "test-fail") -> dict:
        """검증 결과를 먹고 A 사다리를 돌린다.

        `ac_passed=True`면 여기서 멈추고 결과물이 사용자에게 나간다.
        그 결과물이 틀렸다면 다음 사용자 턴에서 B가 잡는다.
        """
        st = self.tasks[task_id]
        if ac_passed:
            st.trace.append(dict(layer="A", step="pass", cost=0.0))
            return dict(layer="A", action="deliver", cost=0.0,
                        reason="AC 통과 — 사용자에게 전달", task=st)

        st.inner_attempts += 1
        if st.inner_attempts >= self.max_inner:
            return dict(layer="A", action="respec", cost=0.0,
                        reason="A 사다리 소진 — 스펙 재정의", task=st)

        d = self.rework.again(task_id, st.last, failure=failure)
        st.last = d
        st.tier_floor = _max_tier(st.tier_floor, d.tier)
        out = 0 if d.tier is Tier.EXTERNAL else REWORK_OUT_TOK
        c = cost_of(d.tier, self.tok_in, out)
        if d.reset:
            c += cost_of(d.tier, RESET_PRIME_TOK, 0)
        st.cost += c
        st.trace.append(dict(layer="A", step=d.step, tier=d.tier.value,
                             scope=d.scope, reset=d.reset, cost=c))
        return dict(layer="A", action="escalate", tier=d.tier, scope=d.scope,
                    reset=d.reset, cost=c, reason=d.reason, task=st)

    def report(self, task_id: str) -> str:
        st = self.tasks[task_id]
        a = sum(1 for t in st.trace if t["layer"] == "A" and t["step"] != "pass")
        b = sum(1 for t in st.trace if t["layer"] == "B")
        return (f"{task_id}: 사용자 턴 {st.turns} · A {a}회 · B {b}회 · "
                f"누적 ${st.cost:.4f} · 최고티어 {st.tier_floor.value}")
