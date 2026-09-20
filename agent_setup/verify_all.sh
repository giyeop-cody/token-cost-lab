#!/usr/bin/env bash
# 서버가 "실제로 뜨고 작동하는가"를 네 층위에서 확인한다.
#
#   1층 내가 만든 프레임으로 프로토콜 왕복        (test_mcp.py)
#   2층 공식 MCP SDK가 클라이언트로 접속          (verify_client.py)
#   3층 공식 Inspector — IDE가 쓰는 바로 그 경로   (npx)
#   4층 설정 파일만 보고 찾아가서 접속            (connect_from_config.py)
#
# 1층만 통과하면 "내 기준에 맞다"는 뜻이고,
# 3층은 Inspector 경유 연결, 4층은 설정 기반 연결을 검사한다.
# 규격 전체 준수나 실제 IDE GUI 작동의 완전한 검증은 별도다.
#
#   bash agent_setup/verify_all.sh
set -uo pipefail

# 서버가 노출하는 도구 수. 도구를 추가하면 여기만 고친다.
EXPECT_TOOLS=6
cd "$(dirname "$0")/.." || exit 1
fail=0
skip=0

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
    skip=$((skip + 1))
    echo "  건너뜀 — pip install mcp 후 다시 실행"
fi

echo
echo "=============================================================="
echo " 3층 — 공식 MCP Inspector (IDE와 동일 경로)"
echo "=============================================================="
if command -v npx >/dev/null 2>&1; then
    tools=$(npx -y @modelcontextprotocol/inspector --cli \
            python3 agent_setup/mcp_server.py --method tools/list 2>/dev/null \
            | grep -c '"name":') || { tools=-1; fail=1; }
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
           2>/dev/null) || { tier="COMMAND_FAILED"; fail=1; }
    if [ "$tier" = "mid" ]; then
        echo "  PASS  Inspector 경유 route_task → tier=mid"
    else
        echo "  FAIL  Inspector 경유 호출 결과 '$tier' (기대 mid)"; fail=1
    fi
else
    skip=$((skip + 1))
    echo "  건너뜀 — node/npx 없음"
fi

echo
echo "=============================================================="
echo " 4층 — 설정 파일에서 출발한 연결 (IDE 기동 경로)"
echo "=============================================================="
if python3 -c "import mcp" 2>/dev/null; then
    python3 agent_setup/connect_from_config.py | tail -12 || fail=1
else
    skip=$((skip + 1))
    echo "  건너뜀 — pip install mcp 후 다시 실행"
fi

echo
echo "=============================================================="
if [ "$fail" -ne 0 ]; then
    echo "  실패 있음."
elif [ "$skip" -gt 0 ]; then
    echo "  실행한 층위 통과 / $skip 층위 미검증 (전체 통과 아님)."
else
    echo "  네 층위 프로토콜 연결 통과 (IDE GUI에서의 수동 확인은 별도)."
fi
echo "=============================================================="
if [ "$fail" -ne 0 ]; then exit 1; fi
if [ "$skip" -gt 0 ]; then exit 2; fi
exit 0
