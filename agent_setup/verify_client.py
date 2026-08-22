#!/usr/bin/env python3
"""공식 MCP SDK로 실제 클라이언트를 붙여 서버를 검증한다.

test_mcp.py는 내가 만든 프레임을 내가 검사한다. 여기서는 반대로,
Anthropic이 배포하는 공식 mcp 패키지가 클라이언트가 되어 우리 서버에
접속한다. IDE가 하는 일과 같은 경로다. 여기서 통과하면 "규격에 맞다"고
말할 근거가 생긴다.

    pip install mcp && python3 verify_client.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).resolve().parent / "mcp_server.py"
P = F = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global P, F
    if cond:
        P += 1
        print(f"  PASS  {label}")
    else:
        F += 1
        print(f"  FAIL  {label}" + (f"  {detail}" if detail else ""))


def data(res) -> dict:
    """공식 클라이언트가 돌려준 결과에서 실제 payload를 꺼낸다."""
    sc = (getattr(res, "structuredContent", None)
          or getattr(res, "structured_content", None))
    if sc:
        return sc
    return json.loads(res.content[0].text)


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])

    print("=" * 62)
    print("공식 MCP SDK 클라이언트로 접속")
    print("=" * 62)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()

            print(f"  서버: {init.server_info.name} v{init.server_info.version}")
            print(f"  프로토콜: {init.protocol_version}")
            print()

            check("공식 SDK가 핸드셰이크를 완료했다",
                  init.server_info.name == "token-router")
            check("서버가 tools capability를 광고한다",
                  init.capabilities.tools is not None)
            check("에이전트에게 줄 지시문이 실려 있다",
                  bool(init.instructions))

            listed = await session.list_tools()
            names = [t.name for t in listed.tools]
            print(f"  노출된 도구: {', '.join(names)}")
            print()

            names = {t.name for t in listed.tools}
            expected = {"route_task", "rework_next", "session_check",
                        "trim_explain", "user_turn", "cost_report"}
            check(f"도구 {len(expected)}개가 SDK 스키마 검증을 통과했다",
                  names == expected,
                  f"누락 {expected - names} · 예상밖 {names - expected}")
            for t in listed.tools:
                check(f"{t.name} — 설명·스키마 유효",
                      bool(t.description) and (t.input_schema or {}).get("type") == "object")

            print()
            print("─" * 62)
            print("실제 도구 호출")
            print("─" * 62)

            r = await session.call_tool(
                "route_task",
                {"task": "정해진 스펙대로 결제 핸들러 구현해줘", "task_id": "live"})
            d = data(r)
            check("route_task 호출 성공", (getattr(r,'isError',None) or getattr(r,'is_error',None) or False) is False)
            check("구현 작업 → mid 티어", d["tier"] == "mid", str(d.get("tier")))
            check("출력 상한이 함께 온다", d["options"].get("max_out_tok") == 2500)
            print(f"    → tier={d['tier']}  ${d['cost_usd']}  "
                  f"절감 ${d['saved_usd']}")

            r = await session.call_tool(
                "route_task",
                {"task": "왜 이 구조가 이렇게 됐는지 근본 원인 분석해줘",
                 "task_id": "live2"})
            d = data(r)
            check("추론 작업 → 정액제 웹 창구", d["tier"] == "web")
            check("웹 위임은 토큰 비용 0", d["cost_usd"] == 0.0)
            print(f"    → tier={d['tier']}  ${d['cost_usd']}")

            steps = []
            for _ in range(4):
                d = data(await session.call_tool("rework_next",
                                                 {"task_id": "live"}))
                steps.append((d["step"], d["tier"], d["scope"],
                              d["reset_session"], d["cost_usd"]))
            print("    사다리:")
            for s, t, sc_, rs, c in steps:
                print(f"      {s:<8} {t:<6} {sc_:<7} "
                      f"reset={'Y' if rs else '-'}  ${c}")
            check("사다리가 순서대로 올라간다",
                  [s[0] for s in steps]
                  == ["retry", "widen", "tier-up", "respec"])
            check("2회차는 맥락을 지킨다 (리셋 없음)", steps[0][3] is False)
            check("4회차에만 티어가 오른다", steps[2][1] == "large")

            d = data(await session.call_tool(
                "session_check",
                {"answer": "끝냈습니다", "done": True,
                 "user_verdict": "이거 말고 아까 방식으로"}))
            check("방향 어긋남을 리셋으로 판정", d["action"] == "reset",
                  str(d.get("action")))
            print(f"    → action={d['action']}  이월={d.get('carry_over')}")

            d = data(await session.call_tool(
                "trim_explain",
                {"text": "\n".join(f"{i}번째 줄입니다." for i in range(1, 7))}))
            check("6줄 설명이 3줄로 잘린다", d["lines_after"] == 3)

            d = data(await session.call_tool("cost_report", {}))
            check("세션 집계가 누적된다", d["routed_tasks"] == 2,
                  str(d.get("routed_tasks")))
            print(f"    → 작업 {d['routed_tasks']}건 · 재시도 {d['rework_turns']}턴"
                  f" · 절감 ${d['saved_usd_vs_always_large']}")

            r = await session.call_tool("rework_next", {"task_id": "없는작업"})
            check("미등록 작업은 오류로 응답 (연결은 유지)",
                  "error" in data(r))

            listed2 = await session.list_tools()
            check("오류 후에도 세션이 살아 있다", len(listed2.tools) == len(expected))

    print()
    print("=" * 62)
    print(f"  {P + F}건 중 {P} PASS / {F} FAIL")
    print("=" * 62)
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
