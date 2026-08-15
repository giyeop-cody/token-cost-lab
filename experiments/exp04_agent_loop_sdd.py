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

반증 (SDD가 항상 이득은 아니다):
  Spec-Kit vs OpenSpec 토큰 벤치마크 — Spec-Kit이 +97~109% 토큰.
  ETH Zurich — LLM 생성 컨텍스트 파일은 성공률을 낮추면서 비용 +20%.
  => "스펙을 써라"가 아니라 "짧고 결정만 담은 스펙을 써라".
  전체 목록: ../SOURCES.md
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab import pricing, report  # noqa: E402


def naive_loop(m, turns, base, per_turn_in, per_turn_out, cached=False):
    """매 턴 전체 이력을 재전송하는 루프의 누적 비용."""
    total = 0.0
    tokens_in = 0
    history = base
    for _ in range(turns):
        tokens_in += history
        cached_part = base if cached else 0
        total += pricing.cost(m, history, per_turn_out, cached_tok=cached_part)
        history += per_turn_in + per_turn_out
    return total, tokens_in


def compacted_loop(m, turns, base, per_turn_in, per_turn_out,
                   every=10, summary=1_500, cached=True):
    """N턴마다 이력을 요약으로 접는 루프."""
    total = 0.0
    tokens_in = 0
    history = base
    for t in range(1, turns + 1):
        tokens_in += history
        total += pricing.cost(m, history, per_turn_out,
                              cached_tok=base if cached else 0)
        history += per_turn_in + per_turn_out
        if t % every == 0:
            # 컴팩션 콜 자체도 비용이다 (입력=현재 이력, 출력=요약)
            total += pricing.cost(m, history, summary,
                                  cached_tok=base if cached else 0)
            history = base + summary
    return total, tokens_in


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet", choices=list(pricing.MODELS))
    ap.add_argument("--turns", type=int, default=20)
    ap.add_argument("--base", type=int, default=8_000,
                    help="시스템 프롬프트 + 툴 정의 + 규약 (고정 프리픽스)")
    ap.add_argument("--turn-in", type=int, default=2_000,
                    help="턴당 새로 들어오는 입력 (툴 결과·파일 내용 등)")
    ap.add_argument("--turn-out", type=int, default=800)
    args = ap.parse_args()

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
    print("  업계 보고: 스펙 없이 시작한 기능은 평균 4~6회 재작업 사이클을 돈다.")
    print("  스펙을 먼저 쓰면 재작업이 60~80% 줄어든다는 보고가 있다.")
    scen = [
        ("스펙 없이 시작 (vibe)", 5, 8, 0),
        ("얕은 지시 + 규약 파일", 3, 8, 1_500),
        ("스펙 먼저 (SDD)", 2, 6, 4_000),
    ]
    rows = []
    base_cost = None
    for name, cycles, turns_per_cycle, spec_tok in scen:
        total = 0.0
        for _ in range(cycles):
            c, _ = naive_loop(m, turns_per_cycle, B + spec_tok, TI, TO, cached=True)
            total += c
        # 스펙 작성 비용도 정직하게 더한다 (사람이 웹 챗에서 정리 + 모델 출력)
        total += pricing.cost(m, 3_000, spec_tok) if spec_tok else 0
        base_cost = base_cost or total
        rows.append([name, cycles, f"{cycles*turns_per_cycle}",
                     f"{spec_tok:,}", pricing.usd(total, 2),
                     "기준" if total == base_cost else f"{(total/base_cost-1)*100:+.0f}%"])
    report.table(["접근", "재작업 사이클", "총 턴", "스펙tok", "기능당 비용", "차이"],
                 rows, ["l", "r", "r", "r", "r", "r"])
    print("  ⚠️ 스펙 작성 자체의 비용도 위 계산에 포함했다. 그래도 SDD가 싸다.")
    print("     이유는 단가가 아니라 '턴 수'가 줄기 때문이다 (A절의 2차 함수).")

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
    print("     외부 보고: 10~15 툴콜마다 압축 시 SWE-bench에서 토큰 22.7% 절감(정확도 유지).")

    report.section("D. YAGNI — 안 쓸 기능의 값")
    print("  '나중에 필요할 것 같아서' 만든 코드는 생성 비용 + 매 턴 재전송 비용을 물린다.")
    rows = []
    for extra_files, label in [(0, "필요한 것만"), (3, "추상화 레이어 3개 추가"),
                               (6, "플러그인 시스템까지")]:
        extra_tok = extra_files * 1_200
        gen = pricing.cost(m, B, extra_tok)                    # 생성 비용
        carry = pricing.cost(m, extra_tok * N, 0, cached_tok=0)  # 이후 턴마다 재전송
        rows.append([label, f"{extra_tok:,}", pricing.usd(gen, 3),
                     pricing.usd(carry, 3), pricing.usd(gen + carry, 3)])
    report.table(["범위", "추가 코드tok", "생성 비용", f"{N}턴 재전송", "합계"],
                 rows, ["l", "r", "r", "r", "r"])
    print("  → 안 쓰는 코드는 한 번 비싼 게 아니라, 세션이 끝날 때까지 계속 과금된다.")

    report.verdict(
        "②·④ 스펙을 먼저 쓰고 범위를 줄이면 토큰이 절약된다",
        "참 — 단, 근거는 '단가'가 아니라 '턴 수'",
        "에이전트 비용은 턴 수의 2차 함수다. 턴 10→20이면 비용은 "
        f"{c20/c10:.1f}배. 스펙은 재작업 사이클을 줄여 이 곡선의 위쪽을 잘라낸다.",
    )
    print("\n  ⚠️ 반대 증거도 있다:")
    print("     · ETH Zurich 연구 — LLM이 생성한 컨텍스트 파일은 성공률을 살짝 떨어뜨리면서")
    print("       추론 비용을 20% 이상 올렸다. 개발자가 쓴 파일도 개선폭은 평균 4%p 수준.")
    print("     · 한 벤치마크에서 Spec-Kit은 OpenSpec 대비 토큰을 최대 2배 썼다.")
    print("     → 결론: '스펙을 쓰라'가 아니라 '짧고 결정만 담은 스펙을 쓰라'.")
    print("       설명(description)이 아니라 결정(decision)을 적을 것.")


if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
