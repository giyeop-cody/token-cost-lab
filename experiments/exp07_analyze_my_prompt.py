# -*- coding: utf-8 -*-
"""
실험 07 — 내 프롬프트 진단기

남의 벤치마크 말고 '내 프롬프트'를 넣어서 재는 도구.
텍스트 파일을 주면 다음을 알려준다:

  1. 토큰 수와 예상 비용
  2. 캐시 프리픽스로 쓸 만한 크기인가
  3. 캐시를 깨뜨리는 동적 값이 앞쪽에 있는가  ← 가장 흔한 실수
  4. 한국어 비중과 그로 인한 토큰 오버헤드
  5. 중복 줄 / 압축 여지
  6. 영어로 바꿨을 때의 절감 추정

실행:
  python experiments/exp07_analyze_my_prompt.py path/to/system_prompt.md
  python experiments/exp07_analyze_my_prompt.py --demo
  echo "..." | python experiments/exp07_analyze_my_prompt.py -

출처:
  Liu et al., "Lost in the Middle", TACL vol.12 (2024)
    — https://arxiv.org/abs/2307.03172
    (컨텍스트 중간의 정보는 회수율이 떨어진다. 핵심 지시는 앞 또는 뒤에.)
  캐시 최소 토큰(1,024) 및 프리픽스 매칭 규칙:
    https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
    https://platform.openai.com/docs/guides/prompt-caching
  전체 목록: ../SOURCES.md
"""

import argparse
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab import pricing, report  # noqa: E402

DEMO = """당신은 우리 회사의 시니어 백엔드 엔지니어를 돕는 코딩 어시스턴트입니다.
현재 시각은 2026-08-14 09:31:07 이며, 요청 ID는 req_8f3a21c9 입니다.
사용자: kim@example.com (세션 a91f-2c88)

## 프로젝트 규약
- 언어는 Python 3.12, 타입 힌트를 반드시 붙입니다.
- 웹 프레임워크는 FastAPI, ORM은 SQLAlchemy 2.0 스타일을 사용합니다.
- 테스트는 pytest, 커버리지 80% 이상을 유지합니다.
- 모든 외부 호출에는 타임아웃과 재시도를 적용합니다.
- 로그는 구조화 로깅(JSON)으로 남기고 PII를 절대 포함하지 않습니다.

## 응답 규칙
- 코드를 먼저 보여주고, 설명은 꼭 필요한 경우에만 짧게 덧붙입니다.
- 코드를 먼저 보여주고, 설명은 꼭 필요한 경우에만 짧게 덧붙입니다.
- 확실하지 않으면 추측하지 말고 무엇을 확인해야 하는지 물어봅니다.

## 아키텍처 개요
서비스는 주문(order), 결제(payment), 배송(shipping) 세 개의 도메인으로 나뉘어 있으며,
각 도메인은 독립된 데이터베이스 스키마를 가집니다. 도메인 간 통신은 이벤트 버스를 통해
비동기로 이루어집니다. 이벤트 버스는 Kafka 기반이며, 각 이벤트는 스키마 레지스트리에
등록된 Avro 스키마를 따릅니다.
"""

DYNAMIC_PATTERNS = [
    (r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", "타임스탬프"),
    (r"\d{4}-\d{2}-\d{2}", "날짜"),
    (r"\b(req|sess|trace|span|txn|id)[-_][A-Za-z0-9]{6,}", "요청/세션 ID"),
    (r"\b[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}", "UUID"),
    (r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "이메일 주소"),
    (r"현재 시각|오늘 날짜|지금은|current time|today is", "시각 참조 문구"),
]

HANGUL = re.compile(r"[\uac00-\ud7a3]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="분석할 텍스트 파일 ('-'는 표준입력)")
    ap.add_argument("--demo", action="store_true", help="예제 프롬프트로 시연")
    ap.add_argument("--model", default="sonnet", choices=list(pricing.MODELS))
    ap.add_argument("--calls", type=int, default=1_000, help="이 프롬프트의 월 호출 수")
    args = ap.parse_args()

    if args.demo or not args.path:
        text, src = DEMO, "내장 데모 프롬프트 (--demo)"
    elif args.path == "-":
        text, src = sys.stdin.read(), "표준입력"
    else:
        with open(args.path, encoding="utf-8") as f:
            text = f.read()
        src = args.path

    try:
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
    except ImportError:
        raise SystemExit("tiktoken 이 필요합니다:  pip install -r requirements.txt")

    m = pricing.get(args.model)
    toks = len(enc.encode(text))
    N = args.calls

    report.title("실험 07 — 내 프롬프트 진단기")
    report.kv("입력", src)
    report.kv("모델 / 월 호출 수", f"{m.name} / {N:,}회")

    report.section("1. 규모와 비용")
    report.kv("글자 수 / 토큰 수", f"{len(text):,}자 / {toks:,} tok")
    base = toks * m.inp / 1e6 * N
    cached = toks * m.inp * m.cache_read / 1e6 * N
    report.kv("월 입력 비용 (캐시 없음)", pricing.usd(base, 2))
    report.kv("월 입력 비용 (캐시 적중)", pricing.usd(cached, 2),
              f"절감 {pricing.usd(base-cached,2)}")

    report.section("2. 캐시 프리픽스 적격성")
    if toks >= 1024:
        print(f"  ✅ {toks:,} tok — 최소 요건(약 1,024 tok)을 넘는다. 캐시 대상으로 적합.")
    else:
        print(f"  ⚠️ {toks:,} tok — 1,024 tok 미만이라 캐시가 적용되지 않을 수 있다.")
        print("     여러 고정 블록(툴 정의·규약·레퍼런스)을 하나로 합쳐 앞에 두는 것을 검토하라.")

    report.section("3. 캐시 파괴 요소 — 앞쪽의 동적 값")
    head_len = max(len(text) // 3, 200)
    head = text[:head_len]
    found = []
    for pat, label in DYNAMIC_PATTERNS:
        for mm in re.finditer(pat, text, re.IGNORECASE):
            pos = mm.start()
            found.append((pos, label, mm.group()[:40], pos < head_len))
    if not found:
        print("  ✅ 동적으로 보이는 값이 발견되지 않았다.")
    else:
        rows = []
        for pos, label, snippet, in_head in sorted(found)[:12]:
            pct = pos / max(len(text), 1) * 100
            rows.append(["🔴 앞부분" if in_head else "🟡 뒷부분",
                         f"{pct:.0f}%", label, snippet])
        report.table(["위치", "문서상 위치", "종류", "값"], rows, ["l", "r", "l", "l"])
        head_hits = sum(1 for f in found if f[3])
        if head_hits:
            print(f"  🔴 앞 1/3 구간에 동적 값 {head_hits}건. 캐시 히트율이 0에 가까워진다.")
            print("     조치: 이 값들을 프롬프트 맨 뒤(사용자 메시지 직전)로 옮겨라.")
            lost = base - cached
            print(f"     방치 시 놓치는 금액: 월 {pricing.usd(lost, 2)}")
        else:
            print("  ✅ 동적 값이 모두 뒤쪽에 있다. 올바른 배치.")

    report.section("4. 언어 구성")
    ko_chars = len(HANGUL.findall(text))
    ratio = ko_chars / max(len(text), 1)
    report.kv("한글 글자 비중", f"{ratio*100:.0f}%", f"({ko_chars:,}자)")
    if ratio > 0.1:
        ko_only = "".join(HANGUL.findall(text))
        ko_tok = len(enc.encode(ko_only))
        report.kv("한글 부분 토큰", f"{ko_tok:,} tok",
                  f"(전체의 {ko_tok/max(toks,1)*100:.0f}%)")
        est = int(ko_tok / 1.44)
        print(f"  이 부분을 영어로 쓰면 대략 {est:,} tok 수준 "
              f"(실험 01의 1.44배 기준, 약 {ko_tok-est:,} tok 절약).")
        print("  ⚠️ 단, 시스템 프롬프트는 '입력'이라 단가가 싸다. 억지로 영어화할 이유는 약하다.")
        print("     영어화의 실익이 큰 곳은 '출력'인 thinking 쪽이다.")

    report.section("5. 중복과 압축 여지")
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 20]
    dup = [(ln, c) for ln, c in Counter(lines).items() if c > 1]
    if dup:
        wasted = sum(len(enc.encode(ln)) * (c - 1) for ln, c in dup)
        print(f"  🟡 완전히 중복된 줄 {len(dup)}종 발견 → {wasted:,} tok 낭비")
        for ln, c in dup[:3]:
            print(f"     x{c}  {ln[:60]}...")
    else:
        print("  ✅ 완전 중복 줄 없음.")
    blank_runs = len(re.findall(r"\n{3,}", text))
    trailing = sum(1 for ln in text.splitlines() if ln != ln.rstrip())
    if blank_runs or trailing:
        print(f"  🟡 연속 빈 줄 {blank_runs}곳, 끝 공백 {trailing}줄 — 사소하지만 매 콜 실린다.")
    long_paras = [p for p in text.split("\n\n") if len(enc.encode(p)) > 200]
    if long_paras:
        print(f"  🟡 200 tok 초과 문단 {len(long_paras)}개 — 불릿/표로 바꾸면 보통 20~40% 줄어든다.")

    report.section("6. 권장 조치 순서")
    todo = []
    if any(f[3] for f in found):
        todo.append("동적 값(시각·ID·이메일)을 프롬프트 맨 뒤로 이동 → 캐시 히트율 확보")
    if toks >= 1024:
        todo.append("이 블록에 캐시 표시(cache_control)를 붙이고 히트율을 대시보드로 확인")
    else:
        todo.append("고정 블록들을 하나로 합쳐 1,024 tok 이상으로 만들기")
    if dup:
        todo.append("중복 줄 제거")
    if long_paras:
        todo.append("긴 산문 문단을 불릿/표로 재작성 (설명이 아니라 결정만 남기기)")
    todo.append("응답의 cache_read_input_tokens 를 로깅해 실제 절감 확인")
    for i, t in enumerate(todo, 1):
        print(f"  {i}. {t}")


if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
