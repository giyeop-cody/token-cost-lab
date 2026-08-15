# -*- coding: utf-8 -*-
"""
실험 03 — 프롬프트 캐싱 (Prompt Caching)

무엇을 재는가:
  (1) 고정 프리픽스를 캐시했을 때 세션 전체 비용 곡선
  (2) 손익분기 — 캐시 쓰기 프리미엄을 몇 번 만에 회수하는가
  (3) 히트율에 따른 절감률
  (4) 캐시를 깨뜨리는 안티패턴의 대가 (동적 값이 프롬프트 앞에 있을 때)

핵심 원칙:
  안정적인 내용을 앞에, 변하는 내용을 뒤에. 캐시는 '프리픽스' 단위로 매칭된다.
  앞쪽에 타임스탬프 하나만 끼워 넣어도 캐시 전체가 무효화된다.

실행:
  python experiments/exp03_prompt_caching.py
  python experiments/exp03_prompt_caching.py --model gpt5 --static 40000 --calls 200

출처:
  Anthropic — Prompt caching
    https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
    (읽기 0.1x, 쓰기 1.25x(5분)/2x(1시간), 최소 1,024 토큰)
  OpenAI — Prompt caching
    https://platform.openai.com/docs/guides/prompt-caching
    (자동 프리픽스 감지, 쓰기 비용 없음)
  Google — Gemini context caching
    https://ai.google.dev/gemini-api/docs/caching
  Liu et al., "Lost in the Middle", TACL vol.12 (2024)
    — https://arxiv.org/abs/2307.03172  (핵심 정보는 앞 또는 뒤에 둘 것)
  전체 목록: ../SOURCES.md
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab import pricing, report  # noqa: E402


def session_cost(m, static, dyn, out, calls, hit_rate=1.0, cached=True):
    """캐시 사용 시 세션 총비용. 첫 콜은 write, 이후는 hit_rate 확률로 read."""
    if not cached:
        return calls * pricing.cost(m, static + dyn, out)
    write = (static * m.inp * m.cache_write + dyn * m.inp + out * m.out) / 1e6
    read = (static * m.inp * m.cache_read + dyn * m.inp + out * m.out) / 1e6
    miss = (static * m.inp * m.cache_write + dyn * m.inp + out * m.out) / 1e6
    rest = calls - 1
    return write + rest * (hit_rate * read + (1 - hit_rate) * miss)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet", choices=list(pricing.MODELS))
    ap.add_argument("--static", type=int, default=20_000, help="고정 프리픽스 토큰")
    ap.add_argument("--dyn", type=int, default=1_000, help="콜마다 바뀌는 입력 토큰")
    ap.add_argument("--out", type=int, default=1_500, help="출력 토큰")
    ap.add_argument("--calls", type=int, default=100)
    args = ap.parse_args()

    m = pricing.get(args.model)
    S, D, O, N = args.static, args.dyn, args.out, args.calls

    report.title("실험 03 — 프롬프트 캐싱")
    report.kv("모델", m.name)
    report.kv("고정 프리픽스", f"{S:,} tok", "(시스템 프롬프트 + 툴 정의 + 레퍼런스)")
    report.kv("가변 입력 / 출력", f"{D:,} tok / {O:,} tok")
    report.kv("세션 콜 수", f"{N:,}")
    report.kv("캐시 단가", f"쓰기 {m.cache_write:g}x · 읽기 {m.cache_read:g}x")

    report.section("A. 벤더별 캐시 정책")
    report.table(
        ["벤더", "읽기 단가", "쓰기 프리미엄", "특징"],
        [["Anthropic", "0.10x", "1.25x", "명시적 cache_control, TTL 5분/1시간"],
         ["OpenAI", "0.50x", "없음", "1,024토큰 이상 프리픽스 자동 적용"],
         ["Google", "0.25x", "있음", "암묵적 + 명시적 컨텍스트 캐시"],
         ["DeepSeek", "0.10x", "없음", "디스크 기반 자동 캐시"]],
    )

    report.section("B. 캐시 유무 세션 비용")
    no_c = session_cost(m, S, D, O, N, cached=False)
    yes_c = session_cost(m, S, D, O, N, hit_rate=1.0)
    report.kv("캐시 없음", pricing.usd(no_c, 2))
    report.kv("캐시 100% 적중", pricing.usd(yes_c, 2),
              f"절감 {(1-yes_c/no_c)*100:.0f}%")

    report.section("C. 히트율에 따른 절감률")
    rows = []
    for hr in (0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 1.0):
        c = session_cost(m, S, D, O, N, hit_rate=hr)
        rows.append([f"{hr*100:.0f}%", pricing.usd(c, 2), f"{(1-c/no_c)*100:+.0f}%"])
    report.table(["히트율", "세션 비용", "절감"], rows, ["r", "r", "r"])
    print("  → 실무 히트율은 안정된 프롬프트 워크로드에서 80~95% 수준으로 보고된다.")
    print("     (한 오픈소스 팀 사례: 히트율 7% → 84% 개선으로 지출 59~70% 감소)")

    report.section("D. 손익분기 — 쓰기 프리미엄은 몇 콜 만에 회수되나")
    if m.cache_write <= 1.0:
        print("  이 벤더는 쓰기 프리미엄이 없다. 첫 재사용부터 바로 이득.")
    else:
        premium = S * m.inp * (m.cache_write - 1) / 1e6
        per_read_save = S * m.inp * (1 - m.cache_read) / 1e6
        be = premium / per_read_save
        report.kv("쓰기 추가 비용", pricing.usd(premium))
        report.kv("읽기 1회당 절약", pricing.usd(per_read_save))
        report.kv("손익분기", f"{be:.2f} 회 재사용",
                  "→ 사실상 두 번째 콜부터 이득")

    report.section("E. 안티패턴 — 캐시를 깨뜨리는 한 줄")
    print("  프롬프트 맨 앞에 '현재 시각: 2026-08-14 09:31:07' 같은 값을 넣으면")
    print("  프리픽스가 매번 달라져 캐시가 전혀 매칭되지 않는다.")
    broken = session_cost(m, S, D, O, N, hit_rate=0.0)
    report.kv("올바른 배치 (동적 값 뒤)", pricing.usd(yes_c, 2))
    report.kv("잘못된 배치 (동적 값 앞)", pricing.usd(broken, 2),
              f"→ {broken/yes_c:.1f}배, +{pricing.usd(broken-yes_c,2)}")
    print("  ⚠️ 쓰기 프리미엄까지 매번 물기 때문에 캐시를 아예 안 쓴 것보다 비쌀 수 있다.")

    report.section("F. 체크리스트")
    for i, t in enumerate([
        "시스템 프롬프트·툴 정의·코딩 규약·레퍼런스 문서를 맨 앞 고정 블록으로 모은다",
        "타임스탬프·요청ID·사용자 입력 등 변하는 값은 반드시 맨 뒤로 보낸다",
        "고정 블록이 최소 1,024토큰(벤더별 상이)을 넘는지 확인한다",
        "툴 정의를 자주 바꾸지 않는다 (툴 1개당 스키마 100~1,000토큰)",
        "응답의 cache_read_input_tokens / cache_creation_input_tokens 를 대시보드로 본다",
        "히트율이 50% 아래면 프롬프트 앞부분에 변동 요소가 있는지 의심한다",
    ], 1):
        print(f"  {i}. {t}")

    report.verdict(
        "프롬프트 캐싱은 실제로 큰 절감을 준다",
        "참 — 단, 프롬프트 구조를 지켜야만",
        f"{m.name} · 프리픽스 {S:,}tok · {N}콜 기준 "
        f"{(1-yes_c/no_c)*100:.0f}% 절감. "
        "다만 동적 값이 앞에 오면 절감은 0이 되고 오히려 손해다.",
    )


if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
