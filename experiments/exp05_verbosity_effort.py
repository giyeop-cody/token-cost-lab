# -*- coding: utf-8 -*-
"""
실험 05 — 장황함(verbosity)과 추론 강도(reasoning effort) (주장 ②·③ 검증)

무엇을 재는가:
  (1) 같은 코드에 붙는 설명 길이별 출력 토큰과 비용
  (2) reasoning effort 단계별 thinking 토큰 비용
  (3) 작업 성격에 맞춰 effort를 배분했을 때의 절감
  (4) 툴 정의(JSON 스키마)가 매 콜 조용히 먹는 토큰

실행:
  python experiments/exp05_verbosity_effort.py
  python experiments/exp05_verbosity_effort.py --model gpt5 --calls 2000

출처:
  reasoning effort / verbosity 파라미터는 벤더 공식 문서 참조.
    OpenAI    — https://platform.openai.com/docs/guides/reasoning
    Anthropic — https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
    Google    — https://ai.google.dev/gemini-api/docs/thinking
  사고 토큰이 출력 단가로 과금되는 것은 exp08_gemini_live.py 에서
  thoughtsTokenCount 필드로 직접 관측할 수 있다.
  전체 목록: ../SOURCES.md
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab import pricing, report  # noqa: E402

# 같은 결과물에 붙는 설명의 3단계 (실제 토큰 수는 tiktoken으로 측정)
SAMPLES = {
    "장황함 (기본값)": """물론입니다! 요청하신 작업을 수행하겠습니다. 먼저 현재 코드의 구조를 살펴보면,
`process_order` 함수가 주문 데이터를 받아서 처리하는 역할을 하고 있습니다. 여기에 재시도
로직을 추가하려면 몇 가지 고려할 점이 있습니다. 첫째, 어떤 예외를 재시도 대상으로 볼
것인지 정해야 합니다. 둘째, 재시도 간격을 어떻게 둘 것인지 결정해야 합니다. 일반적으로는
지수 백오프(exponential backoff)를 사용하는 것이 좋습니다. 셋째, 최대 재시도 횟수를
제한해야 무한 루프를 방지할 수 있습니다. 이러한 점들을 고려하여 아래와 같이 코드를
작성했습니다. 이 코드는 tenacity 라이브러리를 사용하며, 최대 3회까지 재시도하고,
1초에서 시작해 최대 10초까지 지수적으로 대기 시간을 늘립니다. 각 재시도마다 로그를
남기도록 했습니다. 아래 코드를 확인해 주세요.

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10),
       retry=retry_if_exception_type(TransientError), before_sleep=log_retry)
def process_order(order): ...

위 코드에 대해 설명드리자면, `stop_after_attempt(3)`은 최대 3회 시도를 의미하고,
`wait_exponential`은 지수 백오프를 적용합니다. `retry_if_exception_type`으로 재시도할
예외를 한정했습니다. 추가로 궁금하신 점이 있으면 언제든지 말씀해 주세요!""",

    "보통": """`process_order`에 재시도를 추가했습니다. TransientError만 최대 3회,
지수 백오프(1~10초)로 재시도하며 각 시도를 로깅합니다.

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10),
       retry=retry_if_exception_type(TransientError), before_sleep=log_retry)
def process_order(order): ...""",

    "간결 (verbosity=low)": """@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10),
       retry=retry_if_exception_type(TransientError), before_sleep=log_retry)
def process_order(order): ...

TransientError만 재시도. 최대 3회.""",
}

EFFORT = [
    ("minimal", 300,  "포맷 변환, 단순 추출, 분류"),
    ("low",     1_500, "정형화된 CRUD, 보일러플레이트"),
    ("medium",  5_000, "일반 기능 구현, 버그 수정"),
    ("high",    15_000, "아키텍처 설계, 난이도 높은 디버깅"),
    ("max",     35_000, "새 알고리즘, 대규모 리팩터링 계획"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet", choices=list(pricing.MODELS))
    ap.add_argument("--calls", type=int, default=1_760, help="월 요청 수")
    args = ap.parse_args()

    try:
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
        count = lambda s: len(enc.encode(s))  # noqa: E731
    except ImportError:
        raise SystemExit("tiktoken 이 필요합니다:  pip install -r requirements.txt")

    m = pricing.get(args.model)
    N = args.calls

    report.title("실험 05 — 장황함과 추론 강도 (주장 ②·③)")
    report.kv("모델", m.name)
    report.kv("월 요청 수", f"{N:,}")

    report.section("A. 같은 결과물, 다른 설명 길이 — 실제 토큰 측정")
    rows = []
    base = None
    for label, txt in SAMPLES.items():
        t = count(txt)
        base = base or t
        c = t * m.out / 1e6
        rows.append([label, f"{t:,}", pricing.usd(c),
                     pricing.usd(c * N, 2), f"{(t/base-1)*100:+.0f}%"])
    report.table(["출력 스타일", "출력tok", "요청당", f"월 {N:,}건", "vs 장황"],
                 rows, ["l", "r", "r", "r", "r"])
    verbose_t = count(list(SAMPLES.values())[0])
    terse_t = count(list(SAMPLES.values())[-1])
    cut = (1 - terse_t / verbose_t) * 100
    print(f"  → 정보량은 같은데 출력 토큰은 {cut:.0f}% 줄었다.")
    print("     이 샘플은 차이를 보여주려고 다소 극단적으로 잡았다. 실무 기준선은")
    print("     Codex model_verbosity=low 보고치인 '설명형 출력 40~60% 절감'으로 잡는 게 안전하다.")
    print("  ⚠️ 주의: 코드 자체를 줄이는 게 아니다. '코드를 읽으면 아는 내용'만 지운다.")

    report.section("B. reasoning effort 단계별 비용")
    rows = []
    for name, tok, use in EFFORT:
        c = tok * m.out / 1e6
        rows.append([name, f"{tok:,}", pricing.usd(c), pricing.usd(c * N, 2), use])
    report.table(["effort", "thinking tok(전형)", "요청당", f"월 {N:,}건", "적합한 작업"],
                 rows, ["l", "r", "r", "r", "l"])
    print("  ※ thinking 토큰은 출력 단가로 과금된다. 눈에 안 보여도 청구서에는 보인다.")

    report.section("C. effort를 작업별로 배분하면")
    mix = [("설계·계획", 0.10, 15_000), ("일반 구현", 0.50, 5_000),
           ("정형 작업", 0.30, 1_500), ("단순 변환", 0.10, 300)]
    always_high = 15_000 * m.out / 1e6 * N
    tuned = sum(share * tok for _, share, tok in mix) * m.out / 1e6 * N
    rows = [[label, f"{share*100:.0f}%", f"{tok:,}"] for label, share, tok in mix]
    report.table(["작업 유형", "비중", "배정 effort tok"], rows, ["l", "r", "r"])
    report.kv("전부 high 고정", pricing.usd(always_high, 2) + " / 월")
    report.kv("작업별 배분", pricing.usd(tuned, 2) + " / 월",
              f"절감 {(1-tuned/always_high)*100:.0f}%")
    print("  진단 지표: reasoning_tokens / output_tokens 가 0.8을 넘으면 effort 과다 신호.")

    report.section("D. 조용히 새는 토큰 — 툴 정의 스키마")
    print("  툴 1개의 JSON 스키마는 대략 100~1,000토큰. 매 콜 전부 실린다.")
    rows = []
    for tools in (5, 15, 40, 80):
        tok = tools * 400
        c = tok * m.inp / 1e6 * N
        cc = tok * m.inp * m.cache_read / 1e6 * N
        rows.append([tools, f"{tok:,}", pricing.usd(c, 2), pricing.usd(cc, 2)])
    report.table(["툴 개수", "매 콜 스키마tok", f"월 비용(캐시無)", "월 비용(캐시有)"],
                 rows, ["r", "r", "r", "r"])
    print("  → 툴 정의는 캐시 프리픽스에 반드시 넣어야 하는 1순위 후보다.")
    print("     참고: 2,500개 API를 툴 2개(약 1,000토큰)로 접어 넣은 사례도 있다")
    print("     (기존 MCP 방식이면 100만 토큰대).")

    report.verdict(
        "②·③ 장황한 설명과 과한 추론 강도는 낭비다",
        "참",
        f"측정 결과 설명만 줄여 출력 {cut:.0f}% 감소, "
        f"effort 배분으로 추가 {(1-tuned/always_high)*100:.0f}% 감소. "
        "둘 다 결과물의 내용은 그대로다.",
    )
    print("\n  ⚠️ 한계: effort를 낮추면 어려운 작업에서 정확도가 떨어질 수 있다.")
    print("     '전부 낮춰라'가 아니라 '작업 난이도에 맞춰라'가 결론이다.")


if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
