# -*- coding: utf-8 -*-
"""
실험 04 — 에이전트 루프의 2차 함수 비용과 SDD (주장 ②·④ 검증)

무엇을 재는가:
  (1) 대화 이력이 매 턴 재전송되면서 비용이 왜 선형이 아니라 2차 함수로 늘어나는가
  (2) "대충 시작 → 재작업 4~6사이클" vs "스펙 먼저 → 1~2사이클" 총비용
  (3) 컨텍스트 관리 기법(캐싱 / 컴팩션 / 서브에이전트 격리)을 얹었을 때의 곡선
  (4) YAGNI — 안 쓸 기능을 만들 때 버려지는 토큰

핵심:
  턴 N에서의 입력 = 초기 컨텍스트 + (N-1)턴 분량의 누적 이력.
  총 입력 = Σ(1..N) → N^2에 비례한다. 턴 수를 줄이는 것이 단가 협상보다 세다.

실행:
  python experiments/exp04_agent_loop_sdd.py
  python experiments/exp04_agent_loop_sdd.py --model opus --turns 40

출처:
  Anthropic, "Effective context engineering for AI agents" (2025-09)
    https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
    (context rot / attention budget / 컴팩션·노트·서브에이전트,
     서브에이전트는 1,000~2,000 토큰 요약만 반환)
  Anthropic, "How we built our multi-agent research system"
    https://www.anthropic.com/engineering/multi-agent-research-system
    (에이전트는 챗 대비 약 4배, 멀티에이전트는 약 15배 토큰 소모)

외부 반례의 범위 (SDD 대 무스펙으로 혼동하지 않음):
  Spec-Kit vs OpenSpec 토큰 벤치마크 — Spec-Kit이 +97~109% 토큰.
  ETH Zurich — LLM 생성 컨텍스트 파일은 성공률을 낮추면서 비용 +20%.
  => 필요한 결정을 간결히 쓰고, 비용과 품질을 함께 측정하자는 조건부 권장.
  전체 목록: ../SOURCES.md
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab import pricing, report  # noqa: E402

EVIDENCE = "시나리오: 토큰·턴·효과 가정의 비용 계산. 실제 정책 A/B나 품질 동등 절감 실측 아님."


def loop_call_cost(m, history, output, base, cached, warm):
    eligible = cached and pricing.cache_eligible(m, base)
    if not eligible:
        return pricing.cost(m, history, output)
    if warm:
        return pricing.cost(m, history, output, cached_tok=base)
    return pricing.cost(m, history, output) + base*m.inp*(m.cache_write-1)/1e6


def naive_loop(m, turns, base, per_turn_in, per_turn_out, cached=False, warm_cache=False):
    """Independent session. Cold cache by default; warm_cache=True is legacy scenario."""
    total, tokens_in, history = 0.0, 0, base
    for t in range(turns):
        tokens_in += history
        total += loop_call_cost(m, history, per_turn_out, base, cached, warm_cache or t > 0)
        history += per_turn_in + per_turn_out
    return total, tokens_in


def compacted_loop(m, turns, base, per_turn_in, per_turn_out,
                   every=10, summary=1_500, cached=True, warm_cache=False):
    total, tokens_in, history = 0.0, 0, base
    for t in range(1, turns + 1):
        tokens_in += history
        total += loop_call_cost(m, history, per_turn_out, base, cached, warm_cache or t > 1)
        history += per_turn_in + per_turn_out
        if t % every == 0 and t < turns:
            total += loop_call_cost(m, history, summary, base, cached, True)
            tokens_in += history
            history = base + summary
    return total, tokens_in


def sdd_scenarios(m, base=8000, turn_in=2000, turn_out=800, warm_cache=False):
    rows = []
    for name, cycles, turns, spec in (("vibe", 5, 8, 0), ("shallow", 3, 8, 1500), ("sdd", 2, 6, 4000)):
        execution = cycles * naive_loop(m, turns, base+spec, turn_in, turn_out,
                                        cached=True, warm_cache=warm_cache)[0]
        preparation = pricing.cost(m, 3000, spec) if spec else 0
        rows.append(dict(name=name, cycles=cycles, turns=cycles*turns, spec_tokens=spec,
                         execution_usd=execution, spec_preparation_usd=preparation,
                         total_usd=execution+preparation, warm_cache=warm_cache))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet", choices=list(pricing.MODELS))
    ap.add_argument("--turns", type=int, default=20)
    ap.add_argument("--base", type=int, default=8_000,
                    help="시스템 프롬프트 + 툴 정의 + 규약 (고정 프리픽스)")
    ap.add_argument("--turn-in", type=int, default=2_000,
                    help="턴당 새로 들어오는 입력 (툴 결과·파일 내용 등)")
    ap.add_argument("--turn-out", type=int, default=800)
    ap.add_argument("--warm-cache", action="store_true", help="legacy prewarmed-prefix assumption; warm-up cost excluded")
    args = ap.parse_args()
    print(EVIDENCE)

    m = pricing.get(args.model)
    N, B, TI, TO = args.turns, args.base, args.turn_in, args.turn_out

    report.title("실험 04 — 에이전트 루프의 2차 함수 비용과 SDD (주장 ②·④)")
    report.kv("모델", m.name)
    report.kv("고정 프리픽스", f"{B:,} tok")
    report.kv("턴당 신규 입력 / 출력", f"{TI:,} tok / {TO:,} tok")

    report.section("A. 왜 2차 함수인가 — 턴이 늘수록 입력이 눈덩이")
    rows = []
    for n in (5, 10, 20, 30, 50):
        c, ti = naive_loop(m, n, B, TI, TO)
        per_turn_naive = c / n
        rows.append([n, f"{ti:,}", pricing.usd(c, 2), pricing.usd(per_turn_naive, 4)])
    report.table(["턴 수", "누적 입력tok", "총비용", "턴당 평균"],
                 rows, ["r", "r", "r", "r"])
    c10, _ = naive_loop(m, 10, B, TI, TO)
    c20, _ = naive_loop(m, 20, B, TI, TO)
    print(f"  → 턴을 2배(10→20)로 늘리면 비용은 {c20/c10:.1f}배가 된다. 2배가 아니다.")
    print("     '한 번 더 물어보지 뭐'가 싼 행동이 아닌 이유.")

    report.section("B. 재작업 사이클이 만드는 총비용 차이")
    print("  턴 수 40→12는 측정 결과가 아니라 입력 가정이다. 별도 스펙 작성 토큰 비용 포함.")
    print(f"  사이클별 초기 캐시: {'예열됨 (예열 비용 제외, 과거 약 71%)' if args.warm_cache else 'cold, 첫 쓰기 비용 포함'}")
    rows = []
    scenarios = sdd_scenarios(m, B, TI, TO, warm_cache=args.warm_cache)
    base_cost = scenarios[0]["total_usd"]
    for row in scenarios:
        total = row["total_usd"]
        rows.append([row["name"], row["cycles"], row["turns"], f"{row['spec_tokens']:,}",
                     pricing.usd(total, 2), f"{(total/base_cost-1)*100:+.1f}%"])
    report.table(["접근", "재작업 사이클", "총 턴", "스펙tok", "기능당 비용", "차이"],
                 rows, ["l", "r", "r", "r", "r", "r"])
    print("  ⚠️ 스펙 작성 토큰 비용은 포함. 실제 턴 감소·품질 동등성·사람 시간은 미검증.")
    print("     이 가정에서의 절감은 주로 줄어든 턴 수 때문이다. 인과 검증은 별도 실험이 필요하다.")

    report.section("C. 컨텍스트 관리 기법을 얹으면")
    plain, _ = naive_loop(m, N, B, TI, TO, cached=False)
    cached, _ = naive_loop(m, N, B, TI, TO, cached=True)
    comp, _ = compacted_loop(m, N, B, TI, TO, every=10, cached=True)
    comp5, _ = compacted_loop(m, N, B, TI, TO, every=5, cached=True)
    rows = [
        ["아무것도 안 함", pricing.usd(plain, 2), "기준", "—"],
        ["프롬프트 캐싱만", pricing.usd(cached, 2),
         f"{(1-cached/plain)*100:+.0f}%", "프리픽스만 절감. 이력 누적은 그대로"],
        ["캐싱 + 10턴마다 컴팩션", pricing.usd(comp, 2),
         f"{(1-comp/plain)*100:+.0f}%", "요약 콜 비용 포함"],
        ["캐싱 + 5턴마다 컴팩션", pricing.usd(comp5, 2),
         f"{(1-comp5/plain)*100:+.0f}%", "너무 잦으면 요약 콜이 비용을 먹는다"],
    ]
    report.table([f"{N}턴 세션 전략", "총비용", "절감", "비고"], rows,
                 ["l", "r", "r", "l"])
    print("  → 컴팩션 주기에는 최적점이 있다. 무조건 자주 접는다고 싸지지 않는다.")
    print("     주기별 손익은 요약 비용과 품질·재작업 변화를 함께 측정해야 한다.")

    report.section("D. YAGNI — 안 쓸 기능의 값")
    print("  '나중에 필요할 것 같아서' 만든 코드는 생성 비용 + 매 턴 재전송 비용을 물린다.")
    rows = []
    for extra_files, label in [(0, "필요한 것만"), (3, "추상화 레이어 3개 추가"),
                               (6, "플러그인 시스템까지")]:
        extra_tok = extra_files * 1_200
        gen = pricing.cost(m, 0, extra_tok)                    # 생성 비용
        carry = pricing.cost(m, extra_tok * N, 0, cached_tok=0)  # 이후 턴마다 재전송
        rows.append([label, f"{extra_tok:,}", pricing.usd(gen, 3),
                     pricing.usd(carry, 3), pricing.usd(gen + carry, 3)])
    report.table(["범위", "추가 코드tok", "생성 비용", f"{N}턴 재전송", "합계"],
                 rows, ["l", "r", "r", "r", "r"])
    print("  → 안 쓰는 코드는 한 번 비싼 게 아니라, 세션이 끝날 때까지 계속 과금된다.")

    report.verdict(
        "②·④ 스펙을 먼저 쓰고 범위를 줄이면 토큰이 절약된다",
        "조건부 시나리오 — 실제 턴 감소는 미측정",
        "에이전트 비용은 턴 수의 2차 함수다. 턴 10→20이면 비용은 "
        f"{c20/c10:.1f}배. 스펙이 실제 재작업 사이클을 줄인다면 이 누적을 줄일 수 있다.",
    )
    print("\n  ⚠️ 반대 증거도 있다:")
    print("     · ETH Zurich 연구 — LLM이 생성한 컨텍스트 파일은 성공률을 살짝 떨어뜨리면서")
    print("       전체 에이전트 비용을 늘린 조건이 있다 (+20%/+23%, v1). 개발자 파일도 비용은 늘 수 있다.")
    print("     · 외부 블로그 두 사례: Spec-Kit은 OpenSpec 대비 +97~109%. 둘 다 SDD이며 본 저장소의 재현 아님.")
    print("     → 결론: '스펙을 쓰라'가 아니라 '짧고 결정만 담은 스펙을 쓰라'.")
    print("       설명(description)이 아니라 결정(decision)을 적을 것.")


if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
