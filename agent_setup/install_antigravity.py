#!/usr/bin/env python3
"""token-router MCP 서버를 Antigravity에 등록한다.

Antigravity는 버전에 따라 설정 파일 위치가 다르다. 이 스크립트는
존재하는 경로를 전부 찾아 등록하고, 기존 설정은 병합해서 보존한다.

    python3 install_antigravity.py            # 전역 등록
    python3 install_antigravity.py --workspace <경로>   # 워크스페이스 한정
    python3 install_antigravity.py --dry-run  # 무엇이 바뀌는지만 출력
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

HOME = Path.home()
SERVER = (Path(__file__).resolve().parent / "mcp_server.py")

# 버전마다 위치가 달라 실제 보고된 경로를 전부 시도한다.
GLOBAL_CANDIDATES = [
    HOME / ".gemini" / "config" / "mcp_config.json",        # 2.0 / 공식 문서
    HOME / ".gemini" / "antigravity" / "mcp_config.json",   # 1.x IDE
    HOME / ".gemini" / "antigravity-cli" / "mcp_config.json",
]


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        print(f"  !! {path} 가 올바른 JSON이 아니다 — 건너뜀")
        return {}


def register(path: Path, dry: bool) -> bool:
    cfg = load(path)
    servers = cfg.setdefault("mcpServers", {})
    entry = {"command": sys.executable or "python3", "args": [str(SERVER)]}

    if servers.get("token-router") == entry:
        print(f"  = 이미 최신 상태 {path}")
        return False

    existing = len(servers)
    servers["token-router"] = entry

    if dry:
        print(f"  ~ (dry-run) {path} 에 등록 예정 — 기존 서버 {existing}개 유지")
        return True

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():                      # 되돌릴 수 있게 백업
        shutil.copy2(path, path.with_suffix(".json.bak"))
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"  + 등록 {path}  (기존 서버 {existing}개 보존)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", help="이 워크스페이스에만 등록")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not SERVER.exists():
        print(f"오류: {SERVER} 가 없다"); return 1

    print(f"MCP 서버: {SERVER}")
    print()

    if a.workspace:
        targets = [Path(a.workspace).expanduser().resolve()
                   / ".agents" / "mcp_config.json"]
    else:
        # 이미 있는 설정 파일에 모두 등록. 하나도 없으면 공식 경로에 생성.
        targets = [p for p in GLOBAL_CANDIDATES if p.exists()]
        if not targets:
            targets = [GLOBAL_CANDIDATES[0]]
            print("기존 Antigravity 설정을 찾지 못해 공식 경로에 새로 만든다.")

    changed = sum(register(p, a.dry_run) for p in targets)

    print()
    if a.dry_run:
        print("dry-run — 실제로 쓰지 않았다.")
    elif changed:
        print("완료. Antigravity를 재시작하면 도구 5개가 나타난다:")
        print("  route_task · rework_next · session_check · "
              "trim_explain · cost_report")
        print()
        print("AGENTS.md도 워크스페이스에 복사하면 에이전트가 규칙을 따른다:")
        print(f"  cp {Path(__file__).parent / 'antigravity' / 'AGENTS.md'} "
              f"<워크스페이스>/AGENTS.md")
    else:
        print("변경 없음.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
