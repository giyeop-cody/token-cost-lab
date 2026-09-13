#!/usr/bin/env python3
"""설정 파일을 읽어서 거기 적힌 서버에 실제로 붙어본다.

IDE가 켜질 때 하는 일을 그대로 흉내 낸다.

    1. mcp_config.json 을 찾는다   (IDE가 보는 경로 순서대로)
    2. mcpServers 를 파싱한다
    3. 각 서버에 붙어서 initialize → tools/list 를 한다
    4. 붙었는지 / 도구가 몇 개 뜨는지 보고한다

앞선 검증들은 서버 경로를 내가 직접 넘겨줬다. 이 스크립트는 넘겨주지 않는다.
설정 파일만 보고 찾아간다 — 그래서 "설정이 맞게 됐는가"까지 같이 검사한다.

    python3 agent_setup/connect_from_config.py
    python3 agent_setup/connect_from_config.py --config <경로>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    sys.exit("공식 MCP SDK가 없다.  pip install mcp")

# IDE가 설정을 찾는 경로. 위에서부터 순서대로 본다.
CANON = Path.home() / ".gemini/config/mcp_config.json"     # 2.0 전역 (현행)
SEARCH = [
    CANON,
    Path.home() / ".gemini/antigravity/mcp_config.json",   # 1.x 레거시
    Path.home() / ".gemini/antigravity-cli/mcp_config.json",
]

C_OK, C_NO, C_DIM, C_B, C_0 = (
    ("\033[92m", "\033[91m", "\033[90m", "\033[1m", "\033[0m")
    if sys.stdout.isatty() else ("",) * 5
)


def find_config(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.is_file() else None
    for p in SEARCH:
        if p.is_file():
            return p
    return None


def expand(v: str) -> str:
    """${VAR} 치환 — 설정 파일의 비밀값 표기를 IDE와 같게 처리한다."""
    return os.path.expandvars(v) if isinstance(v, str) else v


async def dial(name: str, spec: dict) -> tuple[bool, str, list[str]]:
    """서버 하나에 붙어본다. (성공, 메시지, 도구이름들)"""
    if spec.get("disabled"):
        return True, "disabled — 설정에서 꺼둠", []

    # 원격 서버는 이 스크립트가 다루지 않는다. 왜 안 다루는지는 밝힌다.
    if "serverUrl" in spec:
        return True, f"원격 {spec['serverUrl']} — 인증 필요, 여기선 건너뜀", []

    cmd = expand(spec.get("command", ""))
    if not cmd:
        return False, "command 가 없다", []

    resolved = shutil.which(cmd) or cmd
    if not Path(resolved).exists():
        return False, f"실행 파일을 못 찾음: {cmd}", []

    args = [expand(a) for a in spec.get("args", [])]
    for a in args:
        if a.startswith("/") and not Path(a).exists():
            return False, f"인자 경로가 없다: {a}", []
        if "/ABSOLUTE/PATH/" in a:
            return False, "템플릿 경로가 그대로다 — 실제 경로로 바꿔야 한다", []

    env = {**os.environ, **{k: expand(v)
                            for k, v in (spec.get("env") or {}).items()}}
    params = StdioServerParameters(
        command=resolved, args=args, env=env, cwd=spec.get("cwd"))

    try:
        async with asyncio.timeout(30):
            async with stdio_client(params) as (r, w):
                async with ClientSession(r, w) as s:
                    init = await s.initialize()
                    info = init.server_info
                    tools = (await s.list_tools()).tools
                    off = set(spec.get("disabledTools") or [])
                    names = [t.name for t in tools if t.name not in off]
                    line = (f"{info.name} v{info.version}  "
                            f"프로토콜 {init.protocol_version}")
                    if "route_task" in names:
                        # 뜨는 것과 작동하는 것은 다르다. 한 번 불러본다.
                        r = await s.call_tool(
                            "route_task",
                            {"task": "정해진 스펙대로 구현해줘",
                             "task_id": "probe"})
                        d = (getattr(r, "structured_content", None)
                             or getattr(r, "structuredContent", None) or {})
                        if d.get("tier"):
                            line += (f"\n          호출 확인 route_task → "
                                     f"{d['tier']} · 상한 "
                                     f"{d['options']['max_out_tok']}tok")
                    return True, line, names
    except Exception as e:
        # 실제 원인은 ExceptionGroup 맨 안쪽에 있다.
        cur = e
        while getattr(cur, "exceptions", None):
            cur = cur.exceptions[0]
        return False, f"{type(cur).__name__}: {cur}", []


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help="설정 파일 경로를 직접 지정")
    a = ap.parse_args()

    print(f"\n{C_B}설정 파일을 찾는다{C_0}")
    cfg = find_config(a.config)
    if not cfg:
        print(f"  {C_NO}못 찾음{C_0}. 다음 경로를 봤다:")
        for p in SEARCH:
            print(f"    {C_DIM}{p}{C_0}")
        print("\n  python3 agent_setup/install_antigravity.py 로 만들 수 있다.")
        return 1
    print(f"  {C_OK}찾음{C_0}  {cfg}")
    if not a.config and cfg != CANON:
        # 2.0은 레거시 경로를 조용히 무시한다 — "No MCP Servers"의 최다 원인.
        print(f"  {C_NO}경고{C_0}  레거시 경로다. 2.0은 여기를 안 본다.")
        print(f"        {CANON} 로 옮겨야 인식된다.")

    try:
        servers = json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"]
    except Exception as e:
        print(f"  {C_NO}설정을 읽지 못했다{C_0}: {e}")
        return 1

    print(f"  등록된 서버 {len(servers)}개: {', '.join(servers)}\n")

    print(f"{C_B}하나씩 붙어본다{C_0}")
    bad = 0
    for name, spec in servers.items():
        ok, msg, tools = await dial(name, spec)
        mark = f"{C_OK}연결{C_0}" if ok else f"{C_NO}실패{C_0}"
        print(f"\n  [{mark}] {C_B}{name}{C_0}")
        print(f"          {msg}")
        if tools:
            print(f"          도구 {len(tools)}개")
            for t in tools:
                print(f"            {C_DIM}·{C_0} {t}")
        if not ok:
            bad += 1

    print(f"\n{'=' * 62}")
    if bad:
        print(f"  {C_NO}{bad}개 서버에 붙지 못했다.{C_0}")
    else:
        print(f"  {C_OK}설정에 적힌 서버에 전부 붙었다.{C_0}")
    print(f"{'=' * 62}\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
