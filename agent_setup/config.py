# -*- coding: utf-8 -*-
"""전역 설정 — 사다리 기본값과 리워크 보정 상수를 한 곳에서 관리.

이 파일 하나가 "코드(라이브)와 덱(발표)의 불일치"를 푼다.

1. 기본 사다리는 3칸 축소안(LEAN)이다
    이전까지 Orchestrator / IntentTracker는 7칸 INTENT_LADDER를 기본값으로
    썼다. 그런데 발표 덱은 이미 실로그 검증으로 남은 3칸 축소안을 쓰고 있다.
    라이브 시연(기본 7칸)과 덱(3칸)이 어긋나는 유일한 지점이 이 기본값이었다.
    DEFAULT_INTENT_LADDER_NAME = "lean" 으로 바꾸면 시연이 덱과 정렬된다
    (MCP 서버가 Orchestrator() 기본값을 쓰므로 라이브도 3칸이 된다).

2. 입력 누적이 리워크 비용의 지배항이다
    모델 티어가 아니라 입력 누적이 비용을 지배한다. 실측 페르소나 A 입력은
    79,130토큰까지 불어났다. turn_growth_tok은 그 역산값(오차 5.8%)으로,
    제자리 재시도 시 턴당 4,700토큰씩 컨텍스트에 다시 실리는 것을 모델링한다.
    리셋 칸에서만 0으로 끊긴다 — 리셋의 값어치가 바로 여기서 나온다.

3. 의도불일치 분류를 사다리에 배선한다
    조건부 tier-up은 'reasoning' 종류일 때만 모델을 올린다. 그 판정은
    intent_guard.classify_mismatch가 하고, 워크플로우가 observe()에 넘긴다.
    CLASSIFY_MISMATCH 로 켜고 끈다.
"""
from __future__ import annotations

# 사다리 B 기본값 — 'lean'(3칸 축소안) 또는 'full'(7칸 원안).
# 발표 덱과 맞추려면 'lean' 이 정답이다.
DEFAULT_INTENT_LADDER_NAME: str = "lean"

# A 사다리(router.REWORK_LADDER)는 이미 lean(재시도→범위→모델, 3칸)이다.
# 여기서는 이름만 관리한다.
DEFAULT_REWORK_LADDER_NAME: str = "lean"

# 입력 누적 보정 토큰 — 실측 페르소나 A(79,130토큰) 역산, 오차 5.8%.
# rework_cost_lean() / 워크플로우 비용 산정의 단일 소스.
TURN_GROWTH_TOK: int = 4700

# 의도불일치 분류기를 사다리에 배선할지. 켜면 reasoning 종류만 조건부 tier-up.
CLASSIFY_MISMATCH: bool = True
