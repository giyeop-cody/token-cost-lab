#!/usr/bin/env python3
"""Internal calibration of a COST SCENARIO, not independent live validation.

Fit one total input count, then reproduce cost using exactly the scenario's
Sonnet prices, thought tokens and cache-write assumption. A fit on the same
data is not evidence that the model predicts future agent sessions.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import pricing


def calculate():
    r = json.loads((ROOT / "demo/results.json").read_text(encoding="utf-8"))
    if r["scenario"] != "legacy":
        raise ValueError("This regression reproduces the explicitly labeled legacy scenario")
    a, b = r["A"], r["B"]
    n = a["turns"]
    base = b["in"] / b["turns"]  # approximation, not an observed first prompt
    growth = (a["in"] - n * base) / (n * (n - 1) / 2)
    rounded = round(growth / 100) * 100
    fitted_input = n * base + rounded * n * (n - 1) / 2
    m = pricing.get("sonnet")
    # Legacy A intentionally assumes cache writes on the whole input every time.
    cost = (fitted_input * m.inp * m.cache_write + (a["out"] + a["think"]) * m.out) / 1e6
    return {"evidence_type": "in_sample_scenario_calibration", "base": base,
            "growth_definition": "total input increment INCLUDING previous output, added once",
            "growth_fitted": growth, "growth_rounded": rounded,
            "target_input": a["in"], "fitted_input": fitted_input,
            "input_error_pct": abs(fitted_input / a["in"] - 1) * 100,
            "target_cost": a["cost"], "fitted_cost": cost,
            "cost_error_pct": abs(cost / a["cost"] - 1) * 100,
            "assumptions": {"model": m.name, "input_rate": m.inp, "output_rate": m.out,
                            "write_multiplier": m.cache_write, "thought_tokens": a["think"]},
            "limitation": "same-data fit; neither held-out predictive validation nor live measurement"}


if __name__ == "__main__":
    result = calculate()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    (ROOT / "results/calibration.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
