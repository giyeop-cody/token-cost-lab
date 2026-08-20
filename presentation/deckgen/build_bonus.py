# -*- coding: utf-8 -*-
"""보너스 덱 — 기존 심화 6장 + 신규 확장 슬라이드.

원본 build_deck.py의 보너스 청크를 재사용하고, 앞에 표지를,
뒤에 신규 확장 내용을 덧붙인다.

    python3 presentation/build/build_bonus.py
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
from split_deck import load_chunks, run  # noqa: E402

BONUS_CHUNKS = [16, 17, 18, 19, 20, 21, 25]


def cover():
    sl = kit.blank_slide()
    rect(sl, 0, 0, W, H, fill=BG)
    rect(sl, 0, 0, W, 0.14, fill=WARN)
    text(sl, 1.1, 1.95, 11, 0.4,
         [{'t': 'BONUS TRACK  ·  심화 세션', 'sz': 14, 'b': True, 'c': WARN}])
    text(sl, 1.1, 2.4, 11.5, 1.0,
         [{'t': '견적서의 나머지 항목', 'sz': 52, 'b': True, 'c': FG}])
    text(sl, 1.1, 3.5, 11.5, 0.7,
         [{'t': '원칙 4개로 못 줄인 비용은 어디 있나', 'sz': 30, 'b': True, 'c': ACC}])
    rect(sl, 1.1, 4.5, 1.6, 0.05, fill=WARN)
    text(sl, 1.1, 4.85, 11.4, 1.5, [
        {'t': '캐싱 · 에이전트 루프 · SDD · 라우팅 · 배치 · 압축 — 그리고 240배 실측',
         'sz': 17, 'c': FG},
        {'t': '본편이 “무엇을 시킬까”였다면, 보너스는 “어디서 돌릴까”다. '
              '같은 요청도 실행 위치를 바꾸면 요금이 바뀐다.',
         'sz': 14, 'c': MUTED, 'space_before': 9},
        {'t': '본편 22장을 먼저 보고 오세요. 이 덱은 그 위에 쌓는 레버 모음입니다.',
         'sz': 13.5, 'c': ACC2, 'space_before': 7}])
    note(sl, '토큰 비용 최적화 네트워크 세션 · 보너스 트랙 · github.com/giyeop-cody/token-cost-lab', y=6.6)


# ─────────────────────────────────────────────────────────────
def s_router_vs_rework():
    """용어 정리 — 라우팅 / 리워크 / 워크플로우 컨트롤은 서로 다른 문제다."""
    sl = slide('용어부터 — 라우팅 · 리워크 · 워크플로우 컨트롤', 'BONUS · TAXONOMY')
    text(sl, 0.75, 1.95, 11.9, 0.4,
         [{'t': '셋은 자주 섞여 쓰이지만, 줄이는 비용의 종류가 다르다. 섞으면 처방도 섞인다.',
           'sz': 14.5, 'c': MUTED}])

    card(sl, 0.75, 2.42, 3.85, 2.5, '① 라우팅 (Routing)',
         ['질문: “이 요청을 어느 모델에 보낼까?”',
          '단위: 요청 1건.',
          '줄이는 것: 과잉 스펙 모델에 쓰는 단가.',
          '효과: −49~84% (exp06).'], ACC)
    card(sl, 4.75, 2.42, 3.85, 2.5, '② 리워크 (Rework)',
         ['질문: “왜 같은 걸 다시 시켰나?”',
          '단위: 턴의 반복 횟수.',
          '줄이는 것: 실패한 시도의 재생성.',
          '효과: 48턴 리워크 = 16.6배 (exp09-C).'], RED)
    card(sl, 8.75, 2.42, 3.85, 2.5, '③ 워크플로우 컨트롤',
         ['질문: “이 일을 어떤 순서·형태로 돌릴까?”',
          '단위: 작업 파이프라인 전체.',
          '줄이는 것: 단계 배치의 낭비.',
          '②와 ①을 포함하는 상위 개념.'], ACC2)

    text(sl, 0.75, 5.15, 11.9, 1.0, [
        {'t': '오늘 다루는 것은 ③ 워크플로우 컨트롤이다 — 라우팅은 그 안의 한 수단이다.',
         'sz': 18, 'b': True, 'c': ACC},
        {'t': '“작은 모델로 컨트롤한다”는 것은 값싼 모델이 지휘자를 맡고, 비싼 모델은 '
              '꼭 필요한 구간에만 호출되는 구조를 뜻한다. 리워크 감소는 그 결과로 따라온다.',
         'sz': 14, 'c': MUTED, 'space_before': 9}])
    note(sl, '이 구분은 후속 세션(에이전트 셋팅)의 전제다. 세 가지를 한 단어로 부르면 처방이 뒤섞인다.')


def s_batch_reality():
    """배치 — 24시간 SLO의 현실과 함정."""
    sl = slide('배치 처리 — “24시간”은 상한이지 예정 시각이 아니다', 'BONUS · BATCH')
    y = table(sl, 0.75, 2.05, 7.5,
              ['제공자', '할인', '공식 표현', '실무 관찰'],
              [['OpenAI Batch', ('50%', ACC), '24h 내 완료', '수 분~2h 흔함'],
               ['Gemini Batch', ('50%', ACC), '목표 24h, 대개 더 빠름', '작은 잡은 즉시급'],
               ['Anthropic Batch', ('50%', ACC), '대부분 1h 미만', '캐싱과 중첩 가능'],
               ['xAI Batch', ('50%', ACC), '대개 24h 내', '베스트 에포트']],
              colw=[2.2, 1.0, 2.4, 1.9])

    card(sl, 8.55, 2.05, 4.05, 3.15, '그러나 — 실패 모드가 있다',
         ['2025년 초 OpenAI 배치 지연 사례: 평소 1~2h → 24h 근접, '
          '만료(expired) 비율이 0%대에서 25%↑로 급증한 기간이 보고됨.',
          '',
          '즉 “보통 10분”은 평균이지 보장이 아니다. '
          '마감이 있는 작업에 배치를 쓰려면 폴백 경로가 필요하다.'], WARN)

    text(sl, 0.75, 5.35, 11.9, 1.2, [
        {'t': '규칙: 배치는 “늦어도 되는 일”에만. 늦으면 곤란한 일은 동기 호출로 폴백.',
          'sz': 17.5, 'b': True, 'c': ACC},
        {'t': '적합: 자료조사 · 정규화 · 라벨링 · 임베딩 · 평가 — 사람이 기다리지 않는 작업.  '
              '부적합: 대화 턴 중간, 에이전트 루프 내부(앞 결과가 다음 요청의 입력인 경우).',
          'sz': 14, 'c': MUTED, 'space_before': 9}])
    note(sl, '출처: OpenAI Batch 가이드 · Gemini Batch API 문서 · xAI Batch 문서 · OpenAI 커뮤니티 지연 보고(2025-02)')


def build():
    kit.new_deck()
    chunks = load_chunks()
    cover()
    run(chunks, BONUS_CHUNKS, kit)
    s_router_vs_rework()
    s_batch_reality()
    return kit.save(os.path.join(PRES, '토큰_절약_발표_보너스.pptx'))


if __name__ == '__main__':
    build()
