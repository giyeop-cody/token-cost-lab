# -*- coding: utf-8 -*-
"""후속 덱 — "작은 모델로 워크플로우 컨트롤".

본편/보너스가 "무엇을 시킬까 / 어디서 돌릴까"였다면,
이 덱은 "누가 지휘할까"다. 작은 모델이 오케스트레이터를 맡고,
비싼 모델은 필요한 순간에만 불려 나온다.

    python3 presentation/build/build_agent.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRES = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import deckkit as kit  # noqa: E402
from deckkit import (  # noqa: E402
    ACC, ACC2, BG, CARD, CARD2, FG, LINE, MUTED, RED, WARN, W, H,
    bigstat, bullets, card, note, qr, rect, slide, table, text,
)
from pptx.util import Inches, Pt  # noqa: E402
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR  # noqa: E402

OUT = os.path.join(PRES, '토큰_절약_발표_후속_에이전트셋팅.pptx')


# ── 1. 표지 ──────────────────────────────────────────────────
def cover():
    sl = kit.blank_slide()
    rect(sl, 0, 0, W, H, fill=BG)
    rect(sl, 0, 0, W, 0.14, fill=ACC2)
    text(sl, 1.1, 1.85, 11, 0.4,
         [{'t': 'FOLLOW-UP  ·  에이전트 셋팅편', 'sz': 14, 'b': True, 'c': ACC2}])
    text(sl, 1.1, 2.3, 11.5, 1.0,
         [{'t': '작은 모델이 지휘한다', 'sz': 52, 'b': True, 'c': FG}])
    text(sl, 1.1, 3.42, 11.5, 0.7,
         [{'t': '비싼 모델을 기본값에서 끌어내리는 법', 'sz': 30, 'b': True, 'c': ACC}])
    rect(sl, 1.1, 4.42, 1.6, 0.05, fill=ACC2)
    text(sl, 1.1, 4.78, 11.4, 1.6, [
        {'t': '라우터 · 웹세션 위임 · 3줄 설명 · 배치 · 세션 리셋 — 실제 도는 코드로',
         'sz': 17, 'c': FG},
        {'t': '앞의 두 덱은 “요금을 어떻게 읽는가”였다. 이번엔 그 원칙을 '
              '매 요청마다 자동으로 적용하는 배선을 짠다.',
         'sz': 14, 'c': MUTED, 'space_before': 9},
        {'t': '이 덱의 모든 슬라이드는 agent_setup/router.py 에 대응 코드가 있습니다. '
              '검증 32/32 PASS.',
         'sz': 13.5, 'c': ACC2, 'space_before': 7}])
    note(sl, '토큰 비용 최적화 네트워크 세션 · 후속편 · github.com/giyeop-cody/token-cost-lab', y=6.6)


# ── 2. 문제 재정의 ───────────────────────────────────────────
def s_problem():
    sl = slide('기본값이 비싸다', 'FOLLOW-UP · 문제 재정의')
    text(sl, 0.75, 1.95, 11.9, 0.5,
         [{'t': '대부분의 팀은 "가장 좋은 모델 하나"를 골라 모든 요청에 쓴다. '
               '파일 이름 바꾸기도, 아키텍처 설계도 같은 창구로 간다.',
           'sz': 15.5, 'c': FG}])

    rows = [
        ('파일 rename · grep', '툴 호출', '상위 모델', ('소형 / 코드', ACC)),
        ('결정된 스펙 구현', '코드 생성', '상위 모델', ('중간 모델', ACC)),
        ('방금 짠 코드 설명', '설명', '상위 모델 · 20줄', ('소형 · 3줄', ACC)),
        ('아키텍처 트레이드오프', '추론', '상위 모델 · 사고 ON', ('웹 세션 위임', ACC)),
        ('40개 사이트 정규화', '대량', '상위 모델 · 동기', ('배치 −50%', ACC)),
    ]
    table(sl, 0.75, 2.72, 11.85,
          ['요청', '실제 필요한 능력', '지금 (기본값)', '있어야 할 배선'],
          rows, colw=[3.5, 2.35, 3.0, 3.0], sz=13.5)

    text(sl, 0.75, 5.62, 11.85, 0.9, [
        {'t': '요청의 종류를 판정하는 데 드는 비용은 수십 토큰이다. '
              '상위 모델 호출 한 번만 막아도 즉시 회수된다.',
          'sz': 15, 'b': True, 'c': WARN}])
    note(sl, '앞 덱의 exp06 라우팅 실험: 요청 분배만으로 49~84% 절감. 이 덱은 그 배선을 자동화한다.')


# ── 3. 라우팅 vs 리워크 vs 워크플로우 컨트롤 (사용자 질문 답변) ──
def s_taxonomy():
    sl = slide('당신이 만든 것은 무엇인가', 'FOLLOW-UP · 개념 정리')
    text(sl, 0.75, 1.95, 11.9, 0.4,
         [{'t': '"이게 라우팅인가 리워크 플로우인가"— 셋은 층위가 다르다. '
               '섞어 부르면 처방도 섞인다.', 'sz': 14.5, 'c': MUTED}])

    card(sl, 0.75, 2.45, 3.85, 2.78, '① 라우팅', [
        '요청 1건을 어느 모델로 보낼지 고른다.',
        '대상: 단가 (모델 선택)',
        '효과: −49~84% (exp06)',
        '단위: 요청 하나',
    ], accent=ACC)

    card(sl, 4.78, 2.45, 3.85, 2.78, '② 리워크', [
        '틀려서 되돌아온 일을 다시 시킨다.',
        '대상: 횟수 (턴 반복)',
        '효과: 48턴 = 16.6배 (exp09-C)',
        '단위: 턴의 누적',
    ], accent=RED)

    card(sl, 8.81, 2.45, 3.79, 2.78, '③ 워크플로우 컨트롤', [
        '파이프라인 전체를 지휘한다. ①②를 품는다.',
        '대상: 구조 (무엇을·어디서·몇 번)',
        '효과: 위 둘의 곱',
        '단위: 세션 전체',
    ], accent=ACC2)

    rect(sl, 0.75, 5.45, 11.85, 1.0, fill=CARD, radius=0.06)
    rect(sl, 0.75, 5.45, 0.055, 1.0, fill=ACC2)
    text(sl, 1.1, 5.61, 11.3, 0.78, [
        {'t': '답: 당신이 설계한 것은 ③ 워크플로우 컨트롤이다.', 'sz': 17, 'b': True, 'c': ACC2},
        {'t': '라우팅은 그 안의 한 수단이고, 리워크는 그 컨트롤이 줄이려는 대상이다. '
              '"리워크 플로우"는 되돌아온 작업을 처리하는 흐름을 뜻하므로 목표가 아니라 실패 경로다.',
         'sz': 13.5, 'c': MUTED, 'space_before': 6}])
    note(sl, '용어를 고정하면 측정 지표도 고정된다 — 라우팅은 요청당 단가, 리워크는 턴 수, 컨트롤은 작업당 총비용으로 잰다.')


# ── 4. 전체 아키텍처 ─────────────────────────────────────────
def s_architecture():
    sl = slide('전체 배선도', 'FOLLOW-UP · 아키텍처')
    text(sl, 0.75, 1.9, 11.9, 0.4,
         [{'t': '작은 모델(또는 정규식)이 문 앞에 서서 분류한다. '
               '그 판정 하나로 이후 비용이 결정된다.', 'sz': 14.5, 'c': MUTED}])

    # 입력
    rect(sl, 0.75, 2.5, 2.0, 0.75, fill=CARD, radius=0.06)
    rect(sl, 0.75, 2.5, 0.05, 0.75, fill=FG)
    text(sl, 0.95, 2.72, 1.8, 0.4, [{'t': '사용자 요청', 'sz': 14, 'b': True, 'c': FG}])

    # 라우터
    rect(sl, 3.15, 2.42, 2.3, 0.92, fill=CARD, radius=0.06)
    rect(sl, 3.15, 2.42, 0.05, 0.92, fill=ACC)
    text(sl, 3.36, 2.58, 2.1, 0.6, [
        {'t': '작은 모델 라우터', 'sz': 14, 'b': True, 'c': ACC},
        {'t': '규칙 우선 → 애매하면 SLM', 'sz': 10.5, 'c': MUTED, 'space_before': 3}])

    # 화살표 자리 표시
    text(sl, 2.78, 2.72, 0.4, 0.4, [{'t': '→', 'sz': 18, 'c': MUTED}])
    text(sl, 5.5, 2.72, 0.4, 0.4, [{'t': '→', 'sz': 18, 'c': MUTED}])

    lanes = [
        ('추론', '웹 세션 (Playwright)\n또는 상위 모델', ACC2, '종량 0원 / effort 제한'),
        ('구현', '중간 모델\nverbosity=low', ACC, '조건부 격차 축소'),
        ('설명', '소형 · 3줄 상한\n명시 요청 시만 full', WARN, '−83% (exp05)'),
        ('툴', '소형 · 가능하면 코드\nLLM 없이 결정적 처리', ACC, '호출 자체를 0으로'),
        ('대량', '배치 (24h SLO)\nexpire 폴백 필수', ACC2, '단가 −50%'),
    ]
    y = 3.62
    for i, (name, body, col, eff) in enumerate(lanes):
        yy = y + i * 0.64
        rect(sl, 6.0, yy, 1.15, 0.52, fill=CARD2, radius=0.04)
        text(sl, 6.0, yy + 0.13, 1.15, 0.3,
             [{'t': name, 'sz': 13, 'b': True, 'c': col, 'align': PP_ALIGN.CENTER}])
        text(sl, 7.35, yy + 0.02, 3.3, 0.5,
             [{'t': body.replace('\n', '  ·  '), 'sz': 12, 'c': FG}])
        text(sl, 10.8, yy + 0.06, 1.9, 0.4, [{'t': eff, 'sz': 11.5, 'c': col}])

    # 되먹임
    rect(sl, 0.75, 3.62, 4.7, 1.5, fill=CARD, radius=0.06)
    rect(sl, 0.75, 3.62, 0.05, 1.5, fill=RED)
    text(sl, 1.0, 3.8, 4.4, 1.2, [
        {'t': '세션 메모리 감시', 'sz': 14, 'b': True, 'c': RED},
        {'t': '같은 설명이 2회 반복되면 컨텍스트 오염 신호.',
         'sz': 12, 'c': MUTED, 'space_before': 5},
        {'t': '결론을 파일로 커밋 → 새 세션에서 그 파일만 읽힌다.',
         'sz': 12, 'c': MUTED, 'space_before': 3}])

    text(sl, 0.75, 5.35, 4.7, 0.9, [
        {'t': '반복 설명은 두 배로 손해다.', 'sz': 13.5, 'b': True, 'c': WARN},
        {'t': '출력 토큰을 다시 쓰고, 그 출력이 컨텍스트에 쌓여 '
              '이후 모든 턴의 입력 단가를 올린다.',
         'sz': 12, 'c': MUTED, 'space_before': 4}])
    note(sl, 'agent_setup/router.py — route() 한 함수가 위 분기 전부를 담는다. 의존성 없음, 오프라인 동작.')


# ── 5. 라우터 코드 ───────────────────────────────────────────
def s_router_code():
    sl = slide('라우터 — 실제 코드', 'FOLLOW-UP · 구현 1/3')
    text(sl, 0.75, 1.9, 11.9, 0.4,
         [{'t': '규칙이 먼저다. 정규식으로 잡히면 분류 비용이 0원이다. '
               '못 잡을 때만 소형 모델을 부른다.', 'sz': 14.5, 'c': MUTED}])

    code = [
        'RULES = [   # 순서가 곧 우선순위',
        '  (Kind.TOOL,      r"파일|경로|grep|검색해|커밋"),',
        '  (Kind.BULK,      r"일괄|정규화|라벨링|\\d{2,}(개|건)"),',
        '  (Kind.REASONING, r"설계|아키텍처|트레이드오프"),',
        '  (Kind.EXPLAIN,   r"설명|무슨 뜻|어떻게 동작"),',
        '  (Kind.IMPLEMENT, r"구현|만들어|고쳐|리팩터|버그"),',
        ']',
        '',
        'def route(task, small_llm=None, *,',
        '          allow_external=True):',
        '    kind, by = classify(task, small_llm)',
        '    if kind is Kind.REASONING and allow_external:',
        '        return Decision(kind, Tier.EXTERNAL,',
        '            {"mode": "web-chat"})',
        '    if kind is Kind.IMPLEMENT:',
        '        return Decision(kind, Tier.MID,',
        '            {"explain": "3-lines"})',
    ]
    rect(sl, 0.75, 2.45, 7.15, 3.95, fill=CARD2, radius=0.05)
    rect(sl, 0.75, 2.45, 0.05, 3.95, fill=ACC)
    parts = []
    for i, ln in enumerate(code):
        c = MUTED if ln.strip().startswith('#') or '#' in ln else FG
        if ln.strip().startswith('('):
            c = ACC2
        parts.append({'t': ln or ' ', 'f': 'Consolas', 'sz': 11,
                      'c': c, 'ls': 1.05, 'space_before': 0 if i == 0 else 1})
    text(sl, 1.0, 2.62, 6.85, 3.6, parts)

    card(sl, 8.15, 2.45, 4.45, 1.85, '왜 규칙이 먼저인가', [
        '분류에 LLM을 쓰면 그 자체가 요청당 비용이다.',
        '한국어 업무 요청 대다수는 동사 몇 개로 갈린다.',
        '규칙 미스는 소형 모델이 받는다 — 2단 방어.',
    ], accent=ACC, tsz=14.5, bsz=11.5)

    card(sl, 8.15, 4.5, 4.45, 1.9, '판정 정확도', [
        '한국어 업무 요청 10종 테스트: 10/10 일치.',
        '초기엔 "TODO 전부 grep"을 BULK로 오분류 →',
        'TOOL 규칙을 BULK보다 앞에 두어 해결.',
    ], accent=WARN, tsz=14.5, bsz=11.5)
    note(sl, '오분류 사례를 남겨두는 이유 — 규칙 기반 라우터는 순서 버그가 대부분이다. 테스트가 그것을 잡는다.')


# ── 6. 웹 세션 위임 + 약관 리스크 ────────────────────────────
def s_web_handoff():
    sl = slide('추론은 정액제 창구로 — 그리고 그 대가', 'FOLLOW-UP · 구현 2/3')
    text(sl, 0.75, 1.9, 11.9, 0.4,
         [{'t': '긴 추론은 종량 과금에서 가장 비싼 항목이다. 이미 결제 중인 웹 세션에서 '
               '끝내고 결론만 주입하면 그 항목이 0이 된다.', 'sz': 14.5, 'c': MUTED}])

    rect(sl, 0.75, 2.42, 6.05, 2.15, fill=CARD, radius=0.06)
    rect(sl, 0.75, 2.42, 0.055, 2.15, fill=ACC)
    text(sl, 1.05, 2.6, 5.6, 1.9, [
        {'t': '방법 — 로그인된 세션 재사용', 'sz': 16, 'b': True, 'c': ACC},
        {'t': '1. Playwright로 사용자 프로필 디렉터리를 열어 기존 로그인 쿠키를 그대로 쓴다.',
         'sz': 12.5, 'c': MUTED, 'space_before': 6},
        {'t': '2. 문제 정의를 붙여넣고 응답이 끝날 때까지 대기한다.',
         'sz': 12.5, 'c': MUTED, 'space_before': 3},
        {'t': '3. 결론을 spec.md로 저장 → 중간 모델에 입력으로 주입.',
         'sz': 12.5, 'c': MUTED, 'space_before': 3},
        {'t': '효과: 사고 토큰 과금 0. 앞 덱 실측에서 사고 자동 설정은 240배였다.',
         'sz': 12.5, 'c': ACC, 'space_before': 5}])

    rect(sl, 7.0, 2.42, 5.6, 2.15, fill=CARD, radius=0.06)
    rect(sl, 7.0, 2.42, 0.055, 2.15, fill=RED)
    text(sl, 7.3, 2.6, 5.15, 1.9, [
        {'t': '리스크 — 약관을 먼저 읽어라', 'sz': 16, 'b': True, 'c': RED},
        {'t': 'OpenAI · Google 모두 이용약관에서 자동화된 수단으로의 서비스 접근·'
              '스크래핑을 제한한다. 계정 정지 사유가 될 수 있다.',
         'sz': 12.5, 'c': MUTED, 'space_before': 6},
        {'t': '업무 데이터를 개인 계정 웹 세션에 넣는 것은 별도의 보안·컴플라이언스 문제다.',
         'sz': 12.5, 'c': MUTED, 'space_before': 3},
        {'t': '조직 자산에 이 경로를 넣기 전에 법무·보안 확인을 받을 것.',
         'sz': 12.5, 'c': RED, 'space_before': 5}])

    text(sl, 0.75, 4.78, 11.9, 0.35,
         [{'t': '같은 효과를 내는 합법적 대안 — 이쪽을 기본값으로', 'sz': 15, 'b': True, 'c': ACC2}])
    rows = [
        ('사람이 직접 웹에서 추론', '약관 문제 없음', '수동 복붙 1회', ('권장', ACC)),
        ('API + effort 제한', '완전 합법 · 자동화', '사고 토큰 일부 과금', ('권장', ACC)),
        ('Batch API로 추론 위임', '단가 −50%', '지연 최대 24h', ('조건부', WARN)),
        ('Playwright 자동 조작', '종량 0원', '약관 위반 소지 · 정지 위험', ('비권장', RED)),
    ]
    table(sl, 0.75, 5.2, 11.85, ['경로', '이점', '비용 / 제약', '권고'],
          rows, colw=[3.3, 2.7, 3.55, 2.3], sz=12.5, rowh=0.38)
    note(sl, '이 슬라이드는 "하지 말라"가 아니라 "알고 고르라"는 뜻이다. 개인 실험과 조직 배포의 기준은 다르다.', y=7.02)


# ── 7. 구현 티어 — 주장 정밀화 ───────────────────────────────
def s_impl_tier():
    sl = slide('"결정된 사항은 성능차가 없다"— 절반만 맞다', 'FOLLOW-UP · 검증')
    text(sl, 0.75, 1.9, 11.9, 0.4,
         [{'t': '원안의 주장을 그대로 싣지 않았다. 논문 4편을 확인한 결과, '
               '조건을 붙여야 참이 된다.', 'sz': 14.5, 'c': MUTED}])

    rect(sl, 0.75, 2.4, 5.85, 1.15, fill=CARD2, radius=0.05)
    rect(sl, 0.75, 2.4, 0.05, 1.15, fill=RED)
    text(sl, 1.05, 2.56, 5.4, 0.9, [
        {'t': '원안 (✗)', 'sz': 13, 'b': True, 'c': RED},
        {'t': '"코딩은 이미 결정된 사항에서는 성능차가 없다"',
         'sz': 14.5, 'c': FG, 'space_before': 5}])

    rect(sl, 6.78, 2.4, 5.82, 1.15, fill=CARD2, radius=0.05)
    rect(sl, 6.78, 2.4, 0.05, 1.15, fill=ACC)
    text(sl, 7.08, 2.56, 5.4, 0.9, [
        {'t': '정밀화 (○)', 'sz': 13, 'b': True, 'c': ACC},
        {'t': '세 조건이 동시에 만족될 때 격차가 좁혀지거나 역전된다',
         'sz': 14.5, 'c': FG, 'space_before': 5}])

    conds = [
        ('① 스펙이 확정됐을 때',
         '요구사항 분류 과제에서 8B와 상위 모델의 F1 격차는 평균 0.02. '
         '판단이 끝난 일은 크기를 덜 탄다.'),
        ('② 출력 검증 수단이 있을 때',
         '단위 테스트로 후보를 거를 수 있으면, 고정 컴퓨트 예산에서 '
         '7~13B가 34~70B를 최대 15% 상회한다.'),
        ('③ 임계 크기 이상일 때',
         '3B 미만은 유의하게 떨어진다. 단 Qwen2.5-Coder 1.5B처럼 '
         '7B급을 이기는 반례도 있다 — 크기보다 학습 품질.'),
    ]
    bullets(sl, 0.85, 3.78, 11.7, conds, sz=15.5, gap=0.72)

    rect(sl, 0.75, 6.0, 11.85, 0.82, fill=CARD, radius=0.05)
    rect(sl, 0.75, 6.0, 0.055, 0.82, fill=WARN)
    text(sl, 1.05, 6.14, 11.4, 0.6, [
        {'t': '반대 근거도 같이 본다 — pass@1을 10% 올리려면 VRAM 약 4배가 필요하고, '
              'Rosetta Code 번역에서는 파라미터 수에 따라 성능이 계속 스케일한다. '
              '스펙이 모호하거나 다단계 추론이 필요하면 격차는 그대로 남는다.',
         'sz': 12.5, 'c': MUTED}])
    note(sl, '출처: arXiv 2507.03160 · 2404.00725 · 2510.21443 · Neurocomputing S0925231225021332', y=7.06)


# ── 8. 배치 현실 ─────────────────────────────────────────────
def s_batch():
    sl = slide('배치 — 단가는 반값, 시간은 약속이 아니다', 'FOLLOW-UP · 검증')
    text(sl, 0.75, 1.9, 11.9, 0.4,
         [{'t': '"24시간이라지만 보통 10분 이내 시작"— 이 부분도 확인이 필요했다.',
           'sz': 14.5, 'c': MUTED}])

    rows = [
        ('OpenAI Batch', '−50%', '24시간 내 완료', ('미완 시 expired', RED)),
        ('Google Gemini', '−50%', 'SLO 24시간', ('대형 잡은 분할 권장', WARN)),
        ('xAI', '−50%', '대부분 24시간 내', ('best effort', RED)),
        ('Anthropic', '−50%', '24시간 내', ('대부분 1시간 내 종료', ACC)),
    ]
    table(sl, 0.75, 2.5, 6.5, ['벤더', '할인', '공식 창구', '주의'],
          rows, colw=[1.75, 0.9, 1.85, 1.95], sz=12, rowh=0.42)

    card(sl, 7.45, 2.5, 5.15, 2.05, '실제로 벌어진 일', [
        '2025년 2월, 기존 1~2시간에 끝나던 잡이 24시간에 근접.',
        'expire 비율이 0%에서 25% 이상으로 악화된 사례 다수 보고.',
        '대응: 배치 크기를 절반으로 줄이거나 모델 버전을 고정.',
    ], accent=RED, tsz=15, bsz=12)

    text(sl, 0.75, 4.75, 11.9, 0.35,
         [{'t': '그래서 배치는 세 조건을 모두 만족할 때만 쓴다', 'sz': 15.5, 'b': True, 'c': ACC}])
    conds = [
        ('① 턴 간 의존이 없을 것',
         '에이전트형 다단계 작업은 매 턴 배치 대기가 누적돼 수 시간~수일이 된다. 부적합.'),
        ('② 마감이 없을 것',
         '자료조사 · 분류 · 정규화 · 임베딩처럼 사람이 기다리지 않는 일.'),
        ('③ expire 재시도 경로를 설계할 것',
         '"N시간 내 미완이면 동기 처리로 전환"을 코드에 넣는다 — fallback: sync-after-2h.'),
    ]
    bullets(sl, 0.85, 5.2, 11.7, conds, sz=14.5, gap=0.6)
    note(sl, '출처: OpenAI/Google/xAI 배치 공식 문서 · OpenAI 커뮤니티 지연 스레드(2025-02) · Inspect AI 배치 가이드', y=7.06)


# ── 9. 3줄 설명 + 세션 리셋 ──────────────────────────────────
def s_guards():
    sl = slide('출력을 막는 두 개의 밸브', 'FOLLOW-UP · 구현 3/3')
    text(sl, 0.75, 1.9, 11.9, 0.4,
         [{'t': '프롬프트로 "짧게 답해"라고 부탁하는 것은 지켜지지 않는다. '
               '코드로 잘라야 지켜진다.', 'sz': 14.5, 'c': MUTED}])

    rect(sl, 0.75, 2.42, 6.05, 2.3, fill=CARD, radius=0.06)
    rect(sl, 0.75, 2.42, 0.055, 2.3, fill=WARN)
    text(sl, 1.05, 2.6, 5.6, 2.0, [
        {'t': '밸브 1 — 설명 3줄 상한', 'sz': 16, 'b': True, 'c': WARN},
        {'t': 'def explain_guard(text, max_lines=3):', 'sz': 11.5, 'c': ACC2,
         'f': 'Consolas', 'space_before': 6},
        {'t': '    lines = [비어있지 않은 줄들]', 'sz': 11.5, 'c': FG, 'f': 'Consolas'},
        {'t': '    if len(lines) <= max_lines: return 그대로', 'sz': 11.5, 'c': FG,
         'f': 'Consolas'},
        {'t': '    return 앞 3줄 + "(+N줄 생략 — \'자세히\'로 재요청)"',
         'sz': 11.5, 'c': FG, 'f': 'Consolas'},
        {'t': '구현 직후의 관성적 설명은 소형 모델 + 3줄. '
              '"자세히 / 깊게 / 문서로"가 있을 때만 full.',
         'sz': 12.5, 'c': MUTED, 'space_before': 6}])

    rect(sl, 7.0, 2.42, 5.6, 2.3, fill=CARD, radius=0.06)
    rect(sl, 7.0, 2.42, 0.055, 2.3, fill=RED)
    text(sl, 7.3, 2.6, 5.15, 2.0, [
        {'t': '밸브 2 — 세션 리셋 트리거', 'sz': 16, 'b': True, 'c': RED},
        {'t': '답변을 정규화(공백·문장부호 제거)해 해시로 기록.',
         'sz': 12.5, 'c': MUTED, 'space_before': 6},
        {'t': '같은 해시가 2회 등장 = 메모리에 있는 내용을 다시 생성 중.',
         'sz': 12.5, 'c': MUTED, 'space_before': 3},
        {'t': '→ 결론을 파일로 커밋하고 새 세션 시작. '
              '이월 대상은 specs/*.md와 마지막 결정 사항뿐.',
         'sz': 12.5, 'c': ACC, 'space_before': 3},
        {'t': '표기만 바꾼 재설명도 잡힌다 — "검증합니다." vs "검증합니다!!" 동일 판정.',
         'sz': 12, 'c': MUTED, 'space_before': 5}])

    bigstat(sl, 0.75, 4.95, 3.85, '−83%', '장황 342tok → 간결 58tok (exp05)', color=WARN)
    bigstat(sl, 4.78, 4.95, 3.85, '2회', '동일 설명 반복 시 리셋 발동', color=RED)
    bigstat(sl, 8.81, 4.95, 3.79, '16.6배', '48턴 리워크의 비용 (exp09-C)', color=ACC2)
    note(sl, '리셋을 미루면 손해가 복리로 붙는다 — 재생성한 출력이 다시 입력이 되어 이후 모든 턴의 단가를 올린다.', y=6.75)


# ── 10. 라이브 시연 ──────────────────────────────────────────
def s_demo():
    sl = slide('라이브 — 지금 돌려봅니다', 'FOLLOW-UP · 시연')
    text(sl, 0.75, 1.9, 11.9, 0.4,
         [{'t': 'python3 agent_setup/test_router.py — 의존성 없음. 인터넷 없어도 돕니다.',
           'sz': 14.5, 'c': MUTED}])

    out = [
        '[1] 분류 정확도',
        '  PASS  결제 모듈 아키텍처 설계 트레이드오프 정리해줘  → reasoning',
        '  PASS  스펙대로 핸들러 구현해줘                    → implement',
        '  PASS  방금 짠 코드 설명해줘                       → explain',
        '  PASS  src 밑에서 TODO 전부 grep 해줘             → tool',
        '  PASS  경쟁사 40개 가격 페이지 조사해서 정규화해줘   → bulk',
        '',
        '[2] 라우팅 티어      [3] 설명 3줄 강제',
        '[4] 세션 리셋 트리거  [5] 비용 산식',
        '',
        '        기준선 $0.6500 → 라우팅 $0.0437  (93.3% 절감)',
        '',
        '  32건 중 32 PASS / 0 FAIL',
    ]
    rect(sl, 0.75, 2.45, 7.75, 3.75, fill=CARD2, radius=0.05)
    rect(sl, 0.75, 2.45, 0.05, 3.75, fill=ACC)
    parts = []
    for i, ln in enumerate(out):
        c = ACC if 'PASS' in ln else FG
        if '절감' in ln or 'FAIL' in ln:
            c = WARN
        if ln.startswith('['):
            c = ACC2
        parts.append({'t': ln or ' ', 'f': 'Consolas', 'sz': 12,
                      'c': c, 'space_before': 0 if i == 0 else 2})
    text(sl, 1.02, 2.66, 7.4, 3.4, parts)

    card(sl, 8.75, 2.45, 3.85, 1.95, '시연 순서', [
        '1. router.py — 5개 요청의 행선지',
        '2. test_router.py — 32건 검증',
        '3. 규칙 하나를 깨뜨려 FAIL 재현',
    ], accent=ACC2, tsz=15, bsz=12)

    card(sl, 8.75, 4.55, 3.85, 1.95, '숫자를 읽는 법', [
        '93.3%는 "전부 상위 모델" 대비 추정치다.',
        '실제 절감폭은 요청 구성비에 따라 달라진다.',
        'PRICES 상수를 각자 단가로 바꿔 다시 재라.',
    ], accent=WARN, tsz=15, bsz=12)
    note(sl, 'agent_setup/router.py (라우터) · agent_setup/test_router.py (검증 32건) — 저장소에 그대로 들어 있습니다.', y=6.5)


# ── 11. 도입 순서 ────────────────────────────────────────────
def s_rollout():
    sl = slide('내일부터 뭘 켜나', 'FOLLOW-UP · 도입 순서')
    text(sl, 0.75, 1.9, 11.9, 0.4,
         [{'t': '전부 한 번에 켜지 않는다. 위험이 낮고 효과가 즉시 보이는 것부터.',
           'sz': 14.5, 'c': MUTED}])

    rows = [
        ('1일차', '설명 3줄 상한', '프롬프트 + 후처리 컷', ('즉시 −40~60% 출력', ACC), '없음'),
        ('1주차', '규칙 기반 라우팅', 'route() 붙이고 로그만 남김', ('측정 먼저', ACC2), '오분류'),
        ('2주차', '라우팅 실제 적용', '툴·설명부터 소형으로', ('−49~84%', ACC), '품질 회귀'),
        ('3주차', '세션 리셋 자동화', '반복 감지 → 커밋 → 재시작', ('컨텍스트 단가 억제', ACC), '맥락 유실'),
        ('4주차', '배치 도입', '마감 없는 대량 작업만', ('−50%', ACC), 'expired'),
        ('보류', '웹 세션 자동 조작', '법무 확인 전까지 수동', ('종량 0원', WARN), '약관'),
    ]
    table(sl, 0.75, 2.5, 11.85,
          ['시점', '무엇을', '어떻게', '기대 효과', '주의'],
          rows, colw=[1.15, 2.6, 3.5, 2.7, 1.9], sz=12.5, rowh=0.42)

    rect(sl, 0.75, 5.7, 11.85, 0.95, fill=CARD, radius=0.05)
    rect(sl, 0.75, 5.7, 0.055, 0.95, fill=ACC)
    text(sl, 1.05, 5.86, 11.4, 0.7, [
        {'t': '측정 없이 켜지 마라.', 'sz': 15, 'b': True, 'c': ACC},
        {'t': '1주차에 로그만 남기는 이유가 이것이다. 라우팅 전후의 요청당 비용과 '
              '리워크 턴 수를 같이 재야, 절감이 진짜인지 품질을 팔아 산 것인지 구분된다.',
         'sz': 13, 'c': MUTED, 'space_before': 5}])
    note(sl, '되돌릴 수 있게 만들어라 — route()가 항상 상위 모델을 반환하도록 하는 킬 스위치 하나면 롤백이 끝난다.', y=6.85)


# ── 12. 정리 ─────────────────────────────────────────────────
def s_closing():
    sl = slide('정리', 'FOLLOW-UP · 마무리')

    items = [
        ('작은 모델은 답을 만드는 게 아니라 교통을 정리한다',
         '분류에 드는 수십 토큰이 상위 모델 호출 하나를 막으면 즉시 회수된다.'),
        ('당신이 만든 것은 워크플로우 컨트롤이다',
         '라우팅은 그 안의 수단이고, 리워크는 그것이 줄이려는 대상이다.'),
        ('"성능차 없음"이 아니라 "조건부 격차 축소"다',
         '스펙 확정 · 검증 수단 · 임계 크기 — 셋이 모일 때만 중간 모델로 내려도 안전하다.'),
        ('배치는 단가를 반으로 줄이지만 시간은 약속하지 않는다',
         'expired가 실제로 난다. 폴백 없는 배치는 파이프라인을 멈춘다.'),
        ('밸브는 프롬프트가 아니라 코드로 잠근다',
         '3줄 상한과 세션 리셋은 부탁이 아니라 후처리로 강제해야 지켜진다.'),
    ]
    bullets(sl, 0.85, 2.15, 11.7, items, sz=16.5, gap=0.72)

    rect(sl, 0.75, 5.95, 11.85, 0.9, fill=CARD, radius=0.05)
    rect(sl, 0.75, 5.95, 0.055, 0.9, fill=ACC2)
    text(sl, 1.05, 6.12, 11.4, 0.65, [
        {'t': '세 덱을 관통하는 한 문장 — AI가 나쁜 게 아니라 우리가 견적서를 안 읽은 것이다.',
         'sz': 15.5, 'b': True, 'c': ACC2}])
    note(sl, '본편(22장) · 보너스(10장) · 후속(12장) — 각각 독립 발표 가능합니다.', y=7.02)


# ── 13. QnA ──────────────────────────────────────────────────
def s_qna():
    sl = slide('Q & A', 'FOLLOW-UP')
    text(sl, 0.75, 2.1, 7.6, 0.6,
         [{'t': '코드는 전부 저장소에 있습니다', 'sz': 26, 'b': True, 'c': FG}])
    text(sl, 0.75, 2.85, 7.6, 2.4, [
        {'t': 'agent_setup/router.py — 라우터 · 3줄 밸브 · 세션 메모리 · 비용 추정',
         'sz': 14, 'c': MUTED},
        {'t': 'agent_setup/test_router.py — 검증 32건 (32/32 PASS)',
         'sz': 14, 'c': MUTED, 'space_before': 6},
        {'t': 'presentation/build/ — 이 덱들을 만든 빌드 스크립트 전부',
         'sz': 14, 'c': MUTED, 'space_before': 6},
        {'t': 'PRICES 상수만 각자 단가로 바꾸면 자기 팀 숫자가 나옵니다.',
         'sz': 14, 'c': ACC, 'space_before': 10}])

    text(sl, 0.75, 5.5, 7.6, 0.9, [
        {'t': '가져가실 것 하나만 고르라면 — 설명 3줄 상한.', 'sz': 16, 'b': True, 'c': WARN},
        {'t': '오늘 오후에 켤 수 있고, 되돌리는 데 1분 걸립니다.',
         'sz': 13.5, 'c': MUTED, 'space_before': 5}])

    qr(sl, 9.9, 2.5, size=2.0, caption='github.com/giyeop-cody/token-cost-lab', cw=3.0)
    note(sl, '감사합니다.', y=6.9)


BUILD = [cover, s_problem, s_taxonomy, s_architecture, s_router_code,
         s_web_handoff, s_impl_tier, s_batch, s_guards, s_demo,
         s_rollout, s_closing, s_qna]

if __name__ == '__main__':
    kit.new_deck()
    for fn in BUILD:
        fn()
    kit.save(OUT)
