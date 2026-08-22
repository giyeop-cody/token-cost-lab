#!/usr/bin/env python3
"""라우터를 Antigravity에 물리는 MCP 서버 (stdio, 의존성 0).

Antigravity(IDE / CLI / SDK)는 mcp_config.json에 적힌 프로세스를 띄우고
stdin/stdout으로 JSON-RPC를 주고받는다. 여기서는 router.py의 판단을
그대로 도구 5개로 노출한다.

    route_task      이 작업을 어느 티어로 보낼지 + 출력 옵션
    rework_next     실패했다 — 사다리 다음 칸은 무엇인가
    session_check   지금 계속할지 / 컴팩션할지 / 리셋할지
    trim_explain    설명을 3줄로 자른다
    cost_report     이번 세션에서 무엇을 아꼈나

설계 원칙: 이 서버는 **모델을 대신 호출하지 않는다.**
판단만 돌려주고 실행은 Antigravity 에이전트가 한다. 그래서
API 키가 필요 없고, 어떤 모델을 쓰든 물릴 수 있다.

수동 점검:
    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_server.py
"""
from __future__ import annotations

import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from router import (Tier, route, escalate, explain_guard, cost_of,  # noqa: E402
                    Decision, Kind, ReworkTracker, SessionMemory,
                    REWORK_OUT_TOK, RESET_PRIME_TOK)

SERVER_NAME = "token-router"
SERVER_VERSION = "1.0.0"
PROTOCOL_FALLBACK = "2025-06-18"

# 세션 상태 — Antigravity가 프로세스를 살려두는 동안 유지된다.
from orchestrator import Orchestrator  # noqa: E402

TRACKER = ReworkTracker(max_attempts=5)
MEMORY = SessionMemory()
# 결합 실행기는 자체 ReworkTracker를 들고 있다. rework_next와 상태를
# 공유해야 하므로 같은 인스턴스를 주입한다.
ORCH = Orchestrator(rework=TRACKER, memory=MEMORY)
LAST: dict[str, Decision] = {}
SAVED: list[dict] = []


def log(msg: str) -> None:
    """stdout은 프로토콜 전용이다. 로그는 반드시 stderr로."""
    print(f"[{SERVER_NAME}] {msg}", file=sys.stderr, flush=True)


# ────────────────────────────────────────────────────────────
# 도구 정의
# ────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "route_task",
        "description": (
            "작업을 어느 모델 티어로 보낼지 정한다. 새 작업을 시작하기 전에 "
            "반드시 먼저 호출할 것. 반환된 tier/options를 그대로 따를 것 — "
            "특히 max_out_tok과 explain 옵션은 비용에 직결된다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string",
                         "description": "사용자 요청 원문"},
                "task_id": {"type": "string",
                            "description": "이 작업의 고유 id (리워크 추적용)"},
                "tok_in": {"type": "integer", "default": 1800},
                "tok_out": {"type": "integer", "default": 2500},
            },
            "required": ["task"],
        },
    },
    {
        "name": "rework_next",
        "description": (
            "작업이 실패했을 때 사다리의 다음 칸을 받는다. 같은 방식으로 "
            "무작정 재시도하지 말 것. 한 번에 축 하나만 올린다: "
            "재시도 → 범위 확대 → 모델 티어. reset=true면 새 세션에서 "
            "carry_over만 들고 다시 시작한다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "failure": {"type": "string", "default": "test-fail",
                            "description": "test-fail | lint | timeout | 기타"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "session_check",
        "description": (
            "세션 위생 판정. 매 턴 답변 직후 호출한다. continue면 그대로, "
            "compact면 결론만 남기고 요약, reset이면 새 세션. "
            "완료된 작업이 원하는 방향이 아닐 때만 reset이 나온다 — "
            "반복만으로는 절대 리셋하지 않는다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string",
                           "description": "방금 생성한 답변 본문"},
                "tokens": {"type": "integer", "default": 0},
                "done": {"type": "boolean", "default": False,
                         "description": "작업이 끝났는가"},
                "ac_passed": {"type": "boolean",
                              "description": "완료 시 검증 통과 여부"},
                "user_verdict": {"type": "string",
                                 "description": "완료 시 사용자 반응 원문"},
            },
        },
    },
    {
        "name": "trim_explain",
        "description": (
            "설명을 3줄로 자른다. 명시적으로 '자세히/깊게/문서로'를 "
            "요청받지 않은 모든 설명에 통과시킬 것."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "max_lines": {"type": "integer", "default": 3},
            },
            "required": ["text"],
        },
    },
    {
        "name": "user_turn",
        "description": (
            "사용자 명령이 올 때마다 **가장 먼저** 호출한다. 직전 의도의 "
            "반복인지 판정해 B 사다리를 올리거나, 새 의도면 첫 배정을 낸다. "
            "AC는 통과했는데 사용자가 계속 같은 걸 다시 시키는 상황을 "
            "여기서 잡는다. 반환된 tier/scope로 이번 턴을 실행할 것."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "command": {"type": "string",
                            "description": "사용자가 방금 보낸 명령 원문"},
            },
            "required": ["task_id", "command"],
        },
    },
    {
        "name": "cost_report",
        "description": "이번 세션의 라우팅·리워크·절감액 요약.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ────────────────────────────────────────────────────────────
# 도구 구현
# ────────────────────────────────────────────────────────────
SCOPE_MULT = {"unit": 1.0, "file": 1.6, "module": 2.4, "respec": 1.2}


def _decision_payload(d: Decision, tok_in: int, tok_out: int) -> dict:
    # 범위가 넓어지면 입력이 커지고, 리셋 칸은 이월 문서를 다시 읽힌다.
    # rework_cost()와 같은 셈법을 써야 슬라이드 숫자와 어긋나지 않는다.
    tin = int(tok_in * SCOPE_MULT.get(d.scope, 1.0))
    if d.reset:
        tin += RESET_PRIME_TOK
    out_cap = d.options.get("max_out_tok", tok_out)
    actual = cost_of(d.tier, tin, min(tok_out, out_cap))
    applier = d.options.get("apply_with")
    if applier:                      # 진단은 상위, 적용은 하위 티어
        actual += cost_of(Tier(applier), tin, tok_out)
    naive = cost_of(Tier.LARGE, tin, tok_out)
    return {
        "tier": d.tier.value,
        "kind": d.kind.value,
        "step": d.step,
        "scope": d.scope,
        "attempt": d.attempt,
        "reset_session": d.reset,
        "carry_over": d.carry_over,
        "options": d.options,
        "reason": d.reason,
        "cost_usd": round(actual, 5),
        "if_always_large_usd": round(naive, 5),
        "saved_usd": round(naive - actual, 5),
    }


def t_route_task(args: dict) -> dict:
    task = args["task"]
    tid = args.get("task_id") or f"task-{len(TRACKER.attempts) + 1}"
    ti = int(args.get("tok_in", 1800))
    to = int(args.get("tok_out", 2500))
    d = TRACKER.first(tid, task)
    LAST[tid] = d
    p = _decision_payload(d, ti, to)
    p["task_id"] = tid
    SAVED.append({"id": tid, "saved": p["saved_usd"]})

    hint = [f"티어 {d.tier.value} — {d.reason}"]
    if d.options.get("explain") == "3-lines":
        hint.append("설명은 3줄. 요청받지 않은 해설을 붙이지 말 것.")
    if d.tier is Tier.EXTERNAL:
        hint.append("정액제 웹 세션으로 보낸다. 토큰 과금 없음.")
    if d.options.get("prefer") == "code-execution":
        hint.append("모델에게 시키지 말고 코드로 처리할 것.")
    if d.kind is Kind.BULK:
        hint.append("배치로 보낸다. SLO 24시간 — 마감 있는 작업이면 동기로.")
    p["instruction"] = " / ".join(hint)
    return p


def t_rework_next(args: dict) -> dict:
    tid = args["task_id"]
    prev = LAST.get(tid)
    if prev is None:
        return {"error": f"'{tid}'는 route_task로 시작된 적이 없다. "
                         f"먼저 route_task를 호출할 것."}
    d = TRACKER.again(tid, prev, failure=args.get("failure", "test-fail"))
    LAST[tid] = d
    p = _decision_payload(d, 1800, 2500)
    p["task_id"] = tid

    if d.step == "respec":
        p["instruction"] = ("구현을 멈춘다. 5회차다 — 더 시도하지 말고 "
                            "스펙을 다시 쓰고 사람에게 넘길 것.")
    else:
        bits = [f"{d.attempt}회차 · {d.step} — {d.reason}"]
        cap = d.options.get("max_out_tok")
        if cap:
            bits.append(f"출력 {cap}토큰 상한: 파일 전문을 다시 쓰지 말고 "
                        f"진단 몇 줄 + 통합 diff만 낼 것.")
        if d.options.get("apply_with"):
            bits.append(f"진단만 이 티어에서 받고, 적용은 "
                        f"{d.options['apply_with']}가 한다.")
        if d.reset:
            bits.append(f"새 세션에서 시작. 이월: {d.carry_over}")
        p["instruction"] = " / ".join(bits)
    return p


def t_session_check(args: dict) -> dict:
    ans = args.get("answer", "")
    if args.get("done"):
        r = MEMORY.review(done=True,
                          ac_passed=args.get("ac_passed"),
                          user_verdict=args.get("user_verdict"))
    else:
        r = MEMORY.observe(ans, tokens=int(args.get("tokens", 0)))
    r["turns"] = MEMORY.turns
    r["compactions"] = MEMORY.compactions
    r["resets"] = MEMORY.resets
    if r["action"] == "reset":
        r["reset_prime_tok"] = RESET_PRIME_TOK
    return r


def t_trim_explain(args: dict) -> dict:
    text = args["text"]
    n = int(args.get("max_lines", 3))
    out = explain_guard(text, max_lines=n)
    # 잘린 판정은 글자 수로 하면 안 된다 — 생략 안내문이 붙어서
    # 오히려 길어질 수 있다. 줄 수로 본다.
    before = len(text.strip().splitlines())
    return {"text": out,
            "trimmed": before > n,
            "lines_before": before, "lines_after": min(before, n)}


def t_user_turn(args: dict) -> dict:
    tid = args["task_id"]
    r = ORCH.user_turn(tid, args["command"])
    st = r["task"]
    LAST[tid] = st.last          # rework_next가 이어받을 수 있게 공유
    out = {
        "task_id": tid, "layer": r["layer"], "action": r["action"],
        "tier": r["tier"].value if r.get("tier") else None,
        "scope": r.get("scope"), "reset": r.get("reset", False),
        "est_cost_usd": round(r["cost"], 6),
        "cum_cost_usd": round(st.cost, 6),
        "user_turns": st.turns, "reason": r["reason"],
    }
    if r["action"] == "respec":
        out["instruction"] = (
            "구현을 멈춘다. 같은 의도가 사다리를 다 소진했다 — 모델을 더 "
            "올려도 안 풀린다. 합의된 스펙이 없는 상태이므로 "
            "질문 3개로 스펙을 확정받고 사람에게 넘길 것.")
    elif r["layer"] == "B":
        bits = [f"사용자가 같은 의도를 반복했다 — {r['reason']}"]
        bits.append("같은 범위로 다시 만들지 말 것. 앞 결과물의 어느 부분이 "
                    "의도와 어긋났는지 먼저 짚고 시작할 것.")
        if r.get("reset"):
            bits.append("새 세션에서 시작 — 누적 맥락이 오염됐다. "
                        "범위는 unit으로 되돌리되 모델 티어는 유지한다.")
        out["instruction"] = " / ".join(bits)
    else:
        out["instruction"] = "새 작업이다. 배정된 티어로 첫 구현을 진행할 것."
    return out


def t_cost_report(_args: dict) -> dict:
    saved = sum(s["saved"] for s in SAVED)
    return {
        "routed_tasks": len(TRACKER.attempts),
        "rework_turns": TRACKER.rework_turns(),
        "resets": TRACKER.resets(),
        "compactions": MEMORY.compactions,
        "saved_usd_vs_always_large": round(saved, 4),
        "summary": TRACKER.report(),
        "note": ("절감액은 '모든 작업을 최상위 티어로 보냈을 때' 대비 "
                 "추정치다. 실제 청구서와 대조할 것."),
    }


HANDLERS = {
    "route_task": t_route_task,
    "rework_next": t_rework_next,
    "session_check": t_session_check,
    "trim_explain": t_trim_explain,
    "user_turn": t_user_turn,
    "cost_report": t_cost_report,
}


# ────────────────────────────────────────────────────────────
# JSON-RPC (MCP stdio)
# ────────────────────────────────────────────────────────────
def handle(req: dict) -> dict | None:
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        ver = params.get("protocolVersion") or PROTOCOL_FALLBACK
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": ver,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": (
                "모든 작업은 route_task로 시작한다. 실패하면 같은 방식으로 "
                "재시도하지 말고 rework_next를 부른다. 매 턴 끝에 "
                "session_check를 부른다. 반환된 max_out_tok과 explain "
                "옵션을 반드시 지킬 것 — 리워크 비용의 8할이 출력 토큰이다."
            ),
        }}

    if method in ("notifications/initialized", "initialized", "ping"):
        return None if rid is None else {"jsonrpc": "2.0", "id": rid,
                                         "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        fn = HANDLERS.get(name)
        if fn is None:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32601, "message": f"unknown tool {name}"}}
        try:
            result = fn(args)
        except Exception as exc:                       # noqa: BLE001
            log(traceback.format_exc())
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": f"도구 실패: {exc}"}],
                "isError": True}}
        text = json.dumps(result, ensure_ascii=False, indent=2)
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": text}],
            "structuredContent": result,
            "isError": False}}

    if rid is None:
        return None
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"unknown method {method}"}}


def main() -> None:
    log(f"시작 — 도구 {len(TOOLS)}개")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            log(f"JSON 파싱 실패: {line[:120]}")
            continue
        for one in (req if isinstance(req, list) else [req]):
            resp = handle(one)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
    log("종료")


if __name__ == "__main__":
    main()
