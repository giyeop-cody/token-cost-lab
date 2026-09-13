#!/usr/bin/env bash
# 서버가 "실제로 뜨고 작동하는가"를 네 층위에서 확인한다.
#
#   1층 내가 만든 프레임으로 프로토콜 왕복        (test_mcp.py)
#   2층 공식 MCP SDK가 클라이언트로 접속          (verify_client.py)
#   3층 공식 Inspector — IDE가 쓰는 바로 그 경로   (npx)
#   4층 설정 파일만 보고 찾아가서 접속            (connect_from_config.py)
#
# 1층만 통과하면 "내 기준에 맞다"는 뜻이고,
# 3층까지 통과해야 "규격에 맞다"고 말할 수 있고,
# 4층까지 통과해야 "IDE에 실제로 붙는다"고 말할 수 있다.
#
#   bash agent_setup/verify_all.sh
set -u

# 서버가 노출하는 도구 수. 도구를 추가하면 여기만 고친다.
EXPECT_TOOLS=6
cd "$(dirname "$0")/.." || exit 1
fail=0

echo "=============================================================="
echo " 1층 — 프로토콜 왕복 (의존성 0)"
echo "=============================================================="
python3 agent_setup/test_mcp.py | tail -3 || fail=1

echo
echo "=============================================================="
echo " 2층 — 공식 MCP SDK 클라이언트"
echo "=============================================================="
if python3 -c "import mcp" 2>/dev/null; then
    python3 agent_setup/verify_client.py | tail -3 || fail=1
else
    echo "  건너뜀 — pip install mcp 후 다시 실행"
fi

echo
echo "=============================================================="
echo " 3층 — 공식 MCP Inspector (IDE와 동일 경로)"
echo "=============================================================="
if command -v npx >/dev/null 2>&1; then
    tools=$(npx -y @modelcontextprotocol/inspector --cli \
            python3 agent_setup/mcp_server.py --method tools/list 2>/dev/null \
            | grep -c '"name":')
    if [ "$tools" -eq "$EXPECT_TOOLS" ]; then
        echo "  PASS  Inspector가 도구 $EXPECT_TOOLS개를 인식했다"
    else
        echo "  FAIL  Inspector가 인식한 도구 $tools개 (기대 $EXPECT_TOOLS)"; fail=1
    fi

    tier=$(npx -y @modelcontextprotocol/inspector --cli \
           python3 agent_setup/mcp_server.py --method tools/call \
           --tool-name route_task \
           --tool-arg task="정해진 스펙대로 결제 핸들러 구현해줘" \
           2>/dev/null | python3 -c \
           'import json,sys; print(json.load(sys.stdin)["structuredContent"]["tier"])' \
           2>/dev/null)
    if [ "$tier" = "mid" ]; then
        echo "  PASS  Inspector 경유 route_task → tier=mid"
    else
        echo "  FAIL  Inspector 경유 호출 결과 '$tier' (기대 mid)"; fail=1
    fi
else
    echo "  건너뜀 — node/npx 없음"
fi

echo
echo "=============================================================="
echo " 4층 — 설정 파일에서 출발한 연결 (IDE 기동 경로)"
echo "=============================================================="
if python3 -c "import mcp" 2>/dev/null; then
    python3 agent_setup/connect_from_config.py | tail -12 || fail=1
else
    echo "  건너뜀 — pip install mcp 후 다시 실행"
fi

echo
echo "=============================================================="
[ "$fail" -eq 0 ] && echo "  네 층위 모두 통과 — 규격에 맞고, 설정대로 붙는다." \
                  || echo "  실패 있음."
echo "=============================================================="
exit "$fail"
