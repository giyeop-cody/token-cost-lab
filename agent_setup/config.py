# -*- coding: utf-8 -*-
"""전역 설정 — 에이전트 세팅의 단일 진실 원천.

사다리 축소(Lean) 작업 이후, 런타임 기본값을 한 곳에서 결정한다.
덱은 3칸(widen → reset → respec)으로 발표하므로 라이브 시연도
같은 3칸을 기본으로 쓴다. 기본값을 바꾸려면 이 파일만 고치면 된다.

이 모듈은 ladder_b / router / orchestrator 어느 것도 import 하지 않는다.
(순환 import 방지 — 사다리 선택은 ladder_b.default_ladder()가 한다.)
"""

from __future__ import annotations

# ── 기본 사다리 ────────────────────────────────────────────────
# "lean"  = 3칸 축소 사다리 (LEAN_LADDER: widen → reset → respec)
# "full"  = 7칸 원본 사다리 (INTENT_LADDER)
# 라이브 시연과 덱(이미 3칸)을 정렬하기 위해 기본은 "lean"이다.
DEFAULT_LADDER: str = "lean"

# ── 입력 누적 증가분(토큰) ─────────────────────────────────────
# 리워크가 길어지면 직전 턴 출력 + 사용자 발화가 다음 턴 입력에
# 그대로 다시 실린다. 턴당 이만큼 불어난다고 본다.
# 값의 근거: 실측 페르소나 A 입력 79,130토큰을 등차누적으로 역산.
#   router 비용 모델 재현 오차 5.8% (sonnet $3/$15 + 사고토큰 19,440 기준)
# 리워크 비용의 지배항은 모델 티어가 아니라 이 입력 누적이다.
TURN_GROWTH_TOK: int = 4700

# 입력 누적 지배를 문서/덱에서 인용하는 레퍼런스 수치.
REFERENCE_PERSONA_A_INPUT_TOK: int = 79_130
