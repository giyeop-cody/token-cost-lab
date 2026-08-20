# -*- coding: utf-8 -*-
"""발표_스크립트.md를 본편/보너스로 분할하고 타임코드를 다시 계산한다.

원본 스크립트의 섹션 헤더는 다음 형식이다.

    ## [MM:SS] 슬라이드 N — 제목 (M:SS)

슬라이드 번호 N은 원본 덱의 청크 번호와 1:1로 대응하므로,
split_deck.py와 동일한 MAIN/BONUS 분배를 그대로 적용할 수 있다.
분할하면 앞 슬라이드가 빠지므로 [MM:SS] 시작 시각이 전부 어긋난다.
그래서 각 섹션의 (M:SS) 소요시간을 누적해 타임코드를 새로 찍는다.

    python3 presentation/build/split_script.py
"""
from __future__ import annotations

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PRES = os.path.dirname(HERE)
SRC = os.path.join(PRES, '발표_스크립트.md')

MAIN = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 22, 23, 24, 26, 27]
BONUS = [16, 17, 18, 19, 20, 21, 25]

# 마지막 섹션은 "슬라이드 27~28 ... (나머지)"처럼 분량이 숫자가 아니다.
HDR = re.compile(
    r'^## \[(\d+):(\d\d)\] 슬라이드 ([\d~]+) — (.+?) '
    r'\((?:(\d+):(\d\d)|나머지)\)\s*$', re.M)


def parse(text: str):
    """(머리말, [섹션...], 꼬리말)로 쪼갠다."""
    hits = list(HDR.finditer(text))
    head = text[:hits[0].start()]
    secs = []
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        first = int(re.match(r'\d+', m.group(3)).group())
        secs.append({
            'n': first,
            'label': m.group(3),
            'title': m.group(4),
            # (나머지) 표기는 출처 2장 + Q&A로, 실측상 2분 30초를 배정한다
            'dur': (int(m.group(5)) * 60 + int(m.group(6))
                    if m.group(5) else 150),
            'body': text[m.end():end].rstrip() + '\n',
        })
    # 꼬리말(시간 배분 요약 이후)은 마지막 섹션 본문에서 떼어낸다
    tail = ''
    tm = re.search(r'^## 시간 배분 요약', secs[-1]['body'], re.M)
    if tm:
        tail = secs[-1]['body'][tm.start():]
        secs[-1]['body'] = secs[-1]['body'][:tm.start()].rstrip() + '\n'
    return head, secs, tail


def mmss(sec: int) -> str:
    return f'{sec // 60:02d}:{sec % 60:02d}'


def render(secs, title_block: str, note: str, total_label: str) -> str:
    out = [title_block, '']
    clock = 0
    for i, s in enumerate(secs, 1):
        out.append(f'## [{mmss(clock)}] 슬라이드 {i} — {s["title"]} '
                   f'({s["dur"] // 60}:{s["dur"] % 60:02d})')
        out.append('')
        out.append(s['body'].strip())
        out.append('')
        clock += s['dur']
    out.append('---')
    out.append('')
    out.append('## 시간 배분 요약')
    out.append('')
    out.append(f'| # | 슬라이드 | 시작 | 분량 |')
    out.append('|---|---|---|---|')
    clock = 0
    for i, s in enumerate(secs, 1):
        out.append(f'| {i} | {s["title"]} | {mmss(clock)} | '
                   f'{s["dur"] // 60}:{s["dur"] % 60:02d} |')
        clock += s['dur']
    out.append('')
    out.append(f'**합계 {mmss(clock)}** — {total_label}')
    out.append('')
    out.append(note)
    return '\n'.join(out) + '\n'


BONUS_COVER = {
    'n': 0, 'label': '표지', 'title': '표지 — 견적서의 나머지 항목', 'dur': 40,
    'body': """
> 본편에서 원칙 네 가지를 봤습니다. 그걸로 줄인 게 대략 절반쯤입니다.
> **나머지 절반은 어디 있느냐** — 그게 이 트랙입니다.
>
> 본편이 "무엇을 시킬까"였다면, 보너스는 **"어디서 돌릴까"**입니다.
> 똑같은 요청이라도 캐시에 올리느냐, 배치로 보내느냐, 어느 모델에 태우느냐에
> 따라 요금이 바뀝니다. 내용은 안 바뀌는데 청구서만 바뀌는 겁니다.
>
> 여섯 개 레버를 보고, 마지막에 **240배짜리 실측 하나**로 끝내겠습니다.
""".strip() + '\n',
}

BONUS_TAXONOMY = {
    'n': 0, 'label': '용어', 'title': '용어 정리 — 라우팅 · 리워크 · 워크플로우 컨트롤',
    'dur': 90,
    'body': """
> 질문을 하나 받았습니다. **"이게 라우팅인가요, 리워크 플로우인가요?"**
> 좋은 질문이라 한 장을 따로 만들었습니다. 셋은 층위가 다릅니다.
>
> **첫째, 라우팅.** 요청 하나를 어느 모델로 보낼지 고르는 겁니다.
> 줄이는 대상은 **단가**입니다. 앞서 본 exp06에서 49~84% 나왔습니다.
> 단위는 요청 하나.
>
> **둘째, 리워크.** 같은 걸 다시 시키는 겁니다. 결과가 틀려서 되돌아오는 거죠.
> 줄이는 대상은 **횟수**입니다. 48턴 리워크가 16.6배였습니다.
> 단위는 턴의 누적이고요.
>
> **셋째, 워크플로우 컨트롤.** 파이프라인 전체를 지휘하는 겁니다.
> 앞의 둘을 **수단으로 품습니다.** 무엇을, 어디서, 몇 번 할지를 다 정하니까요.
>
> 그래서 답은 — 이 설계는 **세 번째**입니다. 라우팅은 그 안의 한 수단이고,
> 리워크는 그 컨트롤이 **줄이려는 대상**이지 목표가 아닙니다.
> "리워크 플로우"라는 말은 되돌아온 작업을 처리하는 흐름을 뜻하니까,
> 사실 **실패 경로**에 붙는 이름입니다. 지향할 이름은 아니죠.
>
> 용어를 고정하면 좋은 점이 하나 더 있습니다. **지표가 같이 고정됩니다.**
> 라우팅은 요청당 단가로, 리워크는 턴 수로, 컨트롤은 작업당 총비용으로 잽니다.
> 섞어 부르면 뭘 개선했는지도 못 말하게 됩니다.
""".strip() + '\n',
}

BONUS_BATCH = {
    'n': 0, 'label': '배치', 'title': '배치 처리 — "24시간"은 상한이지 예정 시각이 아니다',
    'dur': 90,
    'body': """
> 배치는 단가가 **정확히 반값**입니다. 네 개 벤더 전부 50% 할인이고,
> 이건 협상 없이 그냥 켜면 나오는 숫자입니다.
>
> 그런데 여기서 흔한 오해가 하나 있습니다.
> **"24시간이라고 써 있지만 보통 10분 안에 시작하더라"** — 저도 그렇게 알고 있었고,
> 그래서 확인해봤습니다. **근거를 못 찾았습니다.**
>
> 공식 문서는 전부 "24시간 내 완료"라고만 합니다. OpenAI는 미완이면
> **expired로 실패** 처리하고, xAI는 아예 **"best effort, 보장 없음"**이라고 씁니다.
> 소규모 잡이 수 초에 끝나는 건 사실입니다. 다만 그건 **관측이지 약속이 아닙니다.**
>
> 실제로 깨진 사례가 있습니다. 2025년 2월에 기존 1~2시간에 끝나던 잡이
> 24시간에 근접했고, **expire 비율이 0%에서 25% 이상으로** 올라간 보고가 여럿 나왔습니다.
> 대응책은 배치 크기를 절반으로 줄이거나 모델 버전을 고정하는 것이었습니다.
>
> 그래서 저는 배치에 **조건 세 개**를 겁니다.
> **하나, 턴 간 의존이 없을 것.** 에이전트처럼 다단계로 도는 작업은
> 매 턴 배치 대기가 쌓여서 며칠이 됩니다. 여기에 쓰면 안 됩니다.
> **둘, 마감이 없을 것.** 자료조사, 분류, 정규화, 임베딩 — 사람이 안 기다리는 일만.
> **셋, expire 재시도 경로를 코드에 넣을 것.** "두 시간 안에 안 끝나면 동기로 전환",
> 이 한 줄이 없으면 반값 할인 받으려다 파이프라인이 멈춥니다.
>
> 정리하면 — **단가는 반값이 맞고, 시간은 약속이 아닙니다.**
""".strip() + '\n',
}


def main():
    text = open(SRC, encoding='utf-8').read()
    head, secs, tail = parse(text)
    by_n = {s['n']: s for s in secs}
    print(f'원본 섹션 {len(secs)}개: {sorted(by_n)}')

    # ── 본편 ────────────────────────────────────────────────
    main_secs = [by_n[n] for n in MAIN if n in by_n]
    main_title = (
        '# “당신이 시켰잖아요” — 시키지도 않은 시공비 청구서\n'
        '### 본편 발표 스크립트 (22장 / 약 25분)\n\n'
        '> 원칙 4개에 집중한 버전입니다. 캐싱·에이전트 루프·SDD·240배 실측은 '
        '보너스 트랙(`발표_스크립트_보너스.md`)으로 분리했습니다.\n'
        '> 질문이 나오면 그쪽 덱을 열어 답하면 됩니다.')
    main_note = (
        '### 시간이 부족할 때 잘라낼 순서\n\n'
        '1. 슬라이드 9 (트레이드오프) — 질문 나오면 그때 설명\n'
        '2. 슬라이드 12 (DRY 5항목 판정) — 결론만 한 줄\n'
        '3. 슬라이드 7 (통계 검정) — "신뢰구간이 1을 안 넘었다"로 압축\n\n'
        '### 시간이 남을 때\n\n'
        '보너스 덱의 240배 실측(슬라이드 8)을 라이브로 돌리세요. '
        '반응이 가장 큰 구간입니다.\n\n'
        '### 준비물\n\n'
        '- 전자칠판에 `토큰_절약_발표_본편.pptx` 로드 (PDF 백업 동봉)\n'
        '- QR용 저장소 주소: github.com/giyeop-cody/token-cost-lab\n'
        '- 보너스·후속 덱을 같은 폴더에 넣어두고 질문 시 즉시 전환')
    main_md = render(main_secs, main_title, main_note, '목표 25분 + Q&A 5분')
    p1 = os.path.join(PRES, '발표_스크립트_본편.md')
    open(p1, 'w', encoding='utf-8').write(main_md)
    print(f'  본편   {len(main_secs):2d}절 → {os.path.basename(p1)} ({len(main_md):,}자)')

    # ── 보너스 ──────────────────────────────────────────────
    # 덱에는 표지·용어정리·배치현실 3장이 새로 들어갔다. 원본 스크립트에
    # 대응 절이 없으므로 여기서 직접 채운다(앞 1절, 뒤 2절).
    bonus_secs = ([BONUS_COVER]
                  + [by_n[n] for n in BONUS if n in by_n]
                  + [BONUS_TAXONOMY, BONUS_BATCH])
    bonus_title = (
        '# 견적서의 나머지 항목\n'
        '### 보너스 트랙 발표 스크립트 (10장 / 약 12분)\n\n'
        '> 본편에서 다루지 못한 레버를 모았습니다. 단독 세션으로도, '
        '본편 뒤에 이어붙여도 됩니다.\n'
        '> 표지·용어정리·배치현실 3장은 이 트랙에서 새로 추가된 슬라이드입니다.')
    bonus_note = (
        '### 이 트랙의 성격\n\n'
        '본편이 “무엇을 시킬까”라면 보너스는 “어디서 돌릴까”입니다. '
        '같은 요청도 실행 위치를 바꾸면 요금이 바뀐다는 이야기로 묶으세요.\n\n'
        '### 준비물\n\n'
        '- `토큰_절약_발표_보너스.pptx`\n'
        '- 240배 실측 라이브 시연을 할 경우 API 키와 네트워크 확인')
    bonus_md = render(bonus_secs, bonus_title, bonus_note, '목표 12분')
    p2 = os.path.join(PRES, '발표_스크립트_보너스.md')
    open(p2, 'w', encoding='utf-8').write(bonus_md)
    print(f'  보너스 {len(bonus_secs):2d}절 → {os.path.basename(p2)} ({len(bonus_md):,}자)')

    dropped = sorted(set(by_n) - set(MAIN) - set(BONUS))
    if dropped:
        print(f'  ※ 미배정 섹션: {dropped}')


if __name__ == '__main__':
    main()
