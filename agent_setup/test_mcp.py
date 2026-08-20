#!/usr/bin/env python3
"""MCP 서버를 실제 프로세스로 띄워 stdio JSON-RPC로 검사한다.

라우터 단위 테스트(test_router.py)와 달리 여기서는 Antigravity가 하는 것과
똑같이 subprocess + stdin/stdout으로 말을 건다. 프로토콜 계약이 깨지면
IDE에서 도구가 아예 안 보이는데, 그건 무대에서 발견할 일이 아니다.

    python3 test_mcp.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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


def talk(requests: list[dict]) -> dict[int, dict]:
    """서버를 띄워 요청을 순서대로 보내고 id별 응답을 모은다."""
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in requests)
    proc = subprocess.run(
        [sys.executable, str(SERVER)], input=payload + "\n",
        capture_output=True, text=True, timeout=60)
    out: dict[int, dict] = {}
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        msg = json.loads(line)
        if msg.get("id") is not None:
            out[msg["id"]] = msg
    return out


def call(i: int, name: str, args: dict) -> dict:
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call",
            "params": {"name": name, "arguments": args}}


def sc(resp: dict) -> dict:
    return resp["result"]["structuredContent"]


print("=" * 60)
print("[1] 프로토콜 핸드셰이크")
print("=" * 60)
r = talk([
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
])
check("initialize 응답", 1 in r)
check("serverInfo.name", r[1]["result"]["serverInfo"]["name"] == "token-router")
check("협상한 프로토콜 버전을 되돌려준다",
      r[1]["result"]["protocolVersion"] == "2025-06-18")
check("tools capability 선언", "tools" in r[1]["result"]["capabilities"])
check("초기화 알림에는 응답하지 않는다(id 없음)", len(r) == 2, str(list(r)))

names = [t["name"] for t in r[2]["result"]["tools"]]
for n in ("route_task", "rework_next", "session_check",
          "trim_explain", "cost_report"):
    check(f"도구 노출 {n}", n in names)
for t in r[2]["result"]["tools"]:
    check(f"{t['name']} 스키마 형식",
          t["inputSchema"]["type"] == "object" and bool(t["description"]))

print()
print("=" * 60)
print("[2] 라우팅 — 종류별 티어")
print("=" * 60)
r = talk([
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    call(10, "route_task", {"task": "정해진 스펙대로 결제 핸들러 구현해줘",
                            "task_id": "impl"}),
    call(11, "route_task", {"task": "이 아키텍처가 왜 이렇게 됐는지 "
                                    "근본 원인을 분석해줘", "task_id": "why"}),
    call(12, "route_task", {"task": "레포에서 TODO 주석 전부 찾아줘",
                            "task_id": "tool"}),
    call(13, "route_task", {"task": "논문 200편 초록을 표로 정규화해줘",
                            "task_id": "bulk"}),
    call(14, "route_task", {"task": "이 함수 뭐 하는 건지 설명해줘",
                            "task_id": "exp"}),
])
check("구현 → mid", sc(r[10])["tier"] == "mid", sc(r[10])["tier"])
check("구현은 3줄 설명 강제",
      sc(r[10])["options"].get("explain") == "3-lines")
check("추론 → 정액제 외부 창구", sc(r[11])["tier"] == "web", sc(r[11])["tier"])
check("외부 창구는 토큰 비용 0", sc(r[11])["cost_usd"] == 0.0)
check("툴 → small", sc(r[12])["tier"] == "small", sc(r[12])["tier"])
check("툴은 코드 실행 우선",
      sc(r[12])["options"].get("prefer") == "code-execution")
check("대량 → batch", sc(r[13])["tier"] == "batch", sc(r[13])["tier"])
check("설명 → small", sc(r[14])["tier"] == "small", sc(r[14])["tier"])
check("모든 배정에 지시문이 붙는다",
      all(sc(r[i])["instruction"] for i in (10, 11, 12, 13, 14)))
check("최상위 고정 대비 절감액을 보고한다", sc(r[10])["saved_usd"] > 0)

print()
print("=" * 60)
print("[3] 리워크 사다리 — 한 번에 축 하나")
print("=" * 60)
reqs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        call(20, "route_task", {"task": "정해진 스펙대로 결제 핸들러 구현해줘",
                                "task_id": "pay"})]
reqs += [call(21 + i, "rework_next", {"task_id": "pay"}) for i in range(4)]
r = talk(reqs)

steps = [sc(r[i])["step"] for i in range(20, 25)]
check("사다리 순서 first→retry→widen→tier-up→respec",
      steps == ["first", "retry", "widen", "tier-up", "respec"], str(steps))
check("2회차는 리셋하지 않는다 — 맥락 보존",
      sc(r[21])["reset_session"] is False)
check("2회차 출력 상한 900", sc(r[21])["options"].get("max_out_tok") == 900)
check("2회차는 티어 유지", sc(r[21])["tier"] == "mid")
check("3회차는 범위만 확대", sc(r[22])["scope"] == "file"
      and sc(r[22])["tier"] == "mid", sc(r[22])["scope"])
check("3회차부터 리셋", sc(r[22])["reset_session"] is True)
check("4회차에 티어 상승", sc(r[23])["tier"] == "large")
check("4회차는 진단만 400토큰",
      sc(r[23])["options"].get("max_out_tok") == 400)
check("4회차 적용은 하위 티어가",
      sc(r[23])["options"].get("apply_with") == "mid")
check("5회차는 구현 중단", sc(r[24])["step"] == "respec")
check("5회차 지시문이 중단을 명시", "멈춘다" in sc(r[24])["instruction"])

# 비용이 rework_cost()와 일치하는지 — 슬라이드 숫자와 어긋나면 안 된다
sys.path.insert(0, str(SERVER.parent))
from router import rework_cost  # noqa: E402

ladder = rework_cost("정해진 스펙대로 결제 핸들러 구현해줘", 1800, 2500,
                     fails=3, strategy="escalate")
mcp_turns = [sc(r[i])["cost_usd"] for i in range(20, 24)]
ref_turns = [round(t["usd"], 5) for t in ladder["trail"]]
check("턴별 비용이 rework_cost()와 일치",
      mcp_turns == ref_turns, f"{mcp_turns} vs {ref_turns}")

check("route_task 없이 rework_next는 거부",
      "error" in sc(talk([
          {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
          call(30, "rework_next", {"task_id": "없음"})])[30]))

print()
print("=" * 60)
print("[4] 세션 위생 — 반복은 컴팩션, 방향 어긋남만 리셋")
print("=" * 60)
same = {"answer": "완전히 동일한 설명 문단", "tokens": 500}
r = talk([
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    call(40, "session_check", same),
    call(41, "session_check", same),
    call(42, "session_check", same),
    call(43, "session_check", {"answer": "끝", "done": True,
                               "ac_passed": False}),
    call(44, "session_check", {"answer": "끝", "done": True,
                               "user_verdict": "이거 말고 아까 방식으로 다시"}),
    call(45, "session_check", {"answer": "끝", "done": True,
                               "ac_passed": True}),
])
check("1회 반복은 계속", sc(r[40])["action"] == "continue")
check("2회 반복도 계속 — 성급히 끊지 않는다",
      sc(r[41])["action"] == "continue")
check("3회 반복은 컴팩션(리셋 아님)", sc(r[42])["action"] == "compact",
      sc(r[42])["action"])
check("컴팩션은 무엇을 남길지 명시", "keep" in sc(r[42]))
check("검증 실패는 리셋이 아니라 리워크",
      sc(r[43])["action"] == "rework", sc(r[43])["action"])
check("방향 어긋남만 리셋", sc(r[44])["action"] == "reset")
check("리셋은 이월 문서를 지정", bool(sc(r[44])["carry_over"]))
check("리셋 재장전 비용을 알려준다",
      sc(r[44])["reset_prime_tok"] == 600)
check("통과하면 계속", sc(r[45])["action"] == "continue")

print()
print("=" * 60)
print("[5] 설명 3줄 강제 · 비용 보고")
print("=" * 60)
r = talk([
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    call(50, "trim_explain", {"text": "한 줄.\n두 줄.\n세 줄.\n네 줄.\n다섯."}),
    call(51, "trim_explain", {"text": "짧은 한 줄."}),
    call(52, "route_task", {"task": "TODO 찾아줘", "task_id": "t1"}),
    call(53, "cost_report", {}),
])
check("5줄 → 3줄", sc(r[50])["lines_after"] == 3)
check("잘렸음을 표시", sc(r[50])["trimmed"] is True)
check("생략 안내가 붙는다", "생략" in sc(r[50])["text"])
check("짧은 설명은 건드리지 않는다", sc(r[51])["trimmed"] is False)
check("비용 보고에 작업 수", sc(r[53])["routed_tasks"] == 1)
check("절감액은 추정치임을 명시", "추정치" in sc(r[53])["note"])

print()
print("=" * 60)
print("[6] 견고성")
print("=" * 60)
r = talk([
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "id": 60, "method": "tools/call",
     "params": {"name": "없는도구", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 61, "method": "없는메서드"},
    {"jsonrpc": "2.0", "id": 62, "method": "ping"},
    call(63, "route_task", {"task": "구현해줘"}),
])
check("모르는 도구는 JSON-RPC 오류", "error" in r[60])
check("모르는 메서드는 JSON-RPC 오류", "error" in r[61])
check("ping 응답", 62 in r and "result" in r[62])
check("task_id 없어도 자동 부여", bool(sc(r[63])["task_id"]))

proc = subprocess.run([sys.executable, str(SERVER)],
                      input='이건 JSON이 아니다\n{"jsonrpc":"2.0","id":1,'
                            '"method":"tools/list"}\n',
                      capture_output=True, text=True, timeout=60)
check("깨진 줄을 만나도 죽지 않는다", proc.returncode == 0)
check("깨진 줄 이후 요청을 계속 처리", '"tools"' in proc.stdout)
check("로그는 stdout을 오염시키지 않는다",
      all(l.strip().startswith("{")
          for l in proc.stdout.splitlines() if l.strip()))
check("로그는 stderr로 나간다", "token-router" in proc.stderr)

print()
print("=" * 60)
print(f"  {P + F}건 중 {P} PASS / {F} FAIL")
print("=" * 60)
sys.exit(1 if F else 0)
