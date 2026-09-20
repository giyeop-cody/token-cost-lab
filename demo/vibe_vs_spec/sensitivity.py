#!/usr/bin/env python3
"""Price sensitivity of ESTIMATED case usage (not cross-model API measurement).

usage.json input and cache are disjoint buckets by this case's definition.
p_in is USD/1M tokens. With cache factor h, delta = p_in/1e6 * (666 + 156*h - 680*r).
Break-even r = (666 + 156*h)/680, NOT universal for every pricing system.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lab import pricing

HERE = Path(__file__).resolve().parent
USAGE = json.loads((HERE / "usage.json").read_text(encoding="utf-8"))


def tokens(label):
    t = USAGE["runs"][label]["tokens"]
    return dict(inp=t["input"], rea=t["reasoning"], out=t["output"], cac=t["cache"])


VIBE, SPEC = tokens("vibe"), tokens("spec")


def cost(u, p_in, p_out, cache_factor=0.1):
    return (u["inp"] * p_in + (u["rea"] + u["out"]) * p_out + u["cac"] * cache_factor * p_in) / 1e6


def calculate():
    h = 0.1
    delta_in, delta_cache = SPEC["inp"]-VIBE["inp"], SPEC["cac"]-VIBE["cac"]
    output_reduction = VIBE["rea"]+VIBE["out"]-SPEC["rea"]-SPEC["out"]
    if output_reduction <= 0:
        raise ValueError("This published break-even formula assumes an output reduction")
    rows = {}
    for key, m in pricing.MODELS.items():
        v, s = cost(VIBE, m.inp, m.out, m.cache_read), cost(SPEC, m.inp, m.out, m.cache_read)
        no_v, no_s = cost(VIBE,m.inp,m.out,1.0), cost(SPEC,m.inp,m.out,1.0)
        rows[key] = {"model": m.name, "ratio": m.ratio, "cache_factor": m.cache_read,
                     "vibe_usd": v, "spec_usd": s, "delta_pct": (s/v-1)*100,
                     "breakeven_ratio": (delta_in+delta_cache*m.cache_read)/output_reduction,
                     "no_cache_vibe_usd": no_v, "no_cache_spec_usd": no_s,
                     "no_cache_delta_pct": (no_s/no_v-1)*100}
    return {"evidence_type": "price_sensitivity_of_estimated_usage", "price_snapshot": "2026-09-20",
            "breakeven_ratio_at_cache_factor_0_1": (delta_in+delta_cache*h)/output_reduction,
            "delta_tokens": {"uncached_input":delta_in,"cached_input":delta_cache,"reasoning_plus_output":-output_reduction},
            "asymptote_pct_at_fixed_cache_factor": -output_reduction/(VIBE["rea"]+VIBE["out"])*100, "models": rows,
            "limitation": "token counts frozen across models; native tokenization, cache eligibility, quality, spec-writing, retries and long-context premiums not verified. No-cache alternative charges all estimated input at the fresh rate."}


def main():
    data = calculate()
    print("고정 usage 추정치의 단가 민감도. 다른 모델에 실제 같은 토큰이 나온다는 뜻이 아님.")
    print("h=0.1일 때 r*=(666+156*h)/680=", data["breakeven_ratio_at_cache_factor_0_1"])
    print("조건부 비교이지 모든 단가 체계·모든 SDD의 절감 보장이 아니다.")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    (HERE / "sensitivity_results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
