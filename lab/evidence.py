"""Recompute publishable numbers from immutable logs and explicit scenarios.

No API calls. Used by reports and slide generation. Tests independently check
key totals/formulas and mutate produced artifacts to test their validators.
"""
import hashlib
import json
from pathlib import Path
import statistics as st

from scipy.stats import norm
from lab import pricing
from tools.stats_test import boot_ratio_ci, cliffs_delta, welch_details
from tools.thinking_sweep import LEVELS, n_correct, wilson
from tools.parallel_tokenizer_bench import measure

ROOT = Path(__file__).resolve().parents[1]


def read_rows(relative):
    return [json.loads(line) for line in (ROOT / relative).read_text(encoding="utf-8").splitlines() if line.strip()]



def verify_sources():
    """Fail on a changed published snapshot; new API runs belong in new files."""
    manifest = json.loads((ROOT / "data/evidence_manifest.json").read_text())
    for path, expected in manifest["files"].items():
        raw = (ROOT / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected["sha256"] or len(raw.splitlines()) != expected["rows"]:
            raise ValueError("Immutable published evidence changed: " + path)


def build():
    verify_sources()
    raw = read_rows("results/live_lang_thinking.jsonl")
    sweep = read_rows("results/thinking_sweep.jsonl")
    if len(raw) != 80 or len(sweep) != 30:
        raise ValueError("Published snapshot must retain 80 language + 30 sweep observations")
    for rows in (raw, sweep):
        if any(r.get("error") or r.get("finish") != "STOP" for r in rows):
            raise ValueError("Stored snapshot expected all STOP; do not silently drop failed observations")
        if {r["model"] for r in rows} != {"gemini-3.1-flash-lite"}:
            raise ValueError("Published snapshot unexpectedly mixes models")
    lang = {}
    for basis in ("actual", "legacy"):
        tasks = {}
        for task in ("explain", "reason"):
            groups = {language: [r for r in raw if r["task"] == task and r["lang"] == language] for language in ("en", "ko")}
            if any(len(g) != 20 for g in groups.values()):
                raise ValueError("Expected 20 repetitions per task/language")
            metrics = {}
            for metric in ("per_call", "per_1000_chars"):
                vals = {language: [pricing.log_cost(r, basis) * (1000/r["chars"] if metric == "per_1000_chars" else 1) for r in group]
                        for language, group in groups.items()}
                t, p, df = welch_details(vals["ko"], vals["en"])
                metrics[metric] = {"en": st.mean(vals["en"]), "ko": st.mean(vals["ko"]),
                                   "ratio_ko_en": st.mean(vals["ko"])/st.mean(vals["en"]),
                                   "ratio_ci95": list(boot_ratio_ci(vals["ko"], vals["en"])),
                                   "welch_t": t, "df": df, "p": p,
                                   "normal_approx_p": float(2*norm.sf(abs(t))),
                                   "bonferroni_4_p": min(1.0, 4*p),
                                   "cliffs_delta": cliffs_delta(vals["ko"], vals["en"])[0]}
            tasks[task] = {"n_each": 20, "metrics": metrics,
                "tokens_chars": {language: {k: st.mean(r[k] for r in g) for k in ("prompt", "thoughts", "cands", "chars")} for language, g in groups.items()}}
        lang[basis] = tasks
    sweep_rows = []
    groups = {budget: [r for r in sweep if r.get("budget") == budget] for _, budget in LEVELS}
    means = {budget: {basis: st.mean(pricing.log_cost(r, basis) for r in g) for basis in ("actual", "legacy")} for budget, g in groups.items()}
    for label, budget in LEVELS:
        g = groups[budget]
        k = n_correct(g)
        sweep_rows.append({"label": label, "budget": budget, "n": len(g), "pass_tolerance_0_05": k,
            "exact_1e_9": n_correct(g, 1e-9), "wilson95": list(wilson(k, len(g))),
            "mean_tokens": {k: st.mean(r[k] for r in g) for k in ("prompt", "thoughts", "cands")},
            "cost_per_call": means[budget], "ratio_to_unspecified": {b: means[budget][b]/means[None][b] for b in means[budget]},
            "thoughts_min": min(r["thoughts"] for r in g), "thoughts_max": max(r["thoughts"] for r in g)})
    ratios = {basis: {"auto_unspecified": means[-1][basis]/means[None][basis], "auto_zero": means[-1][basis]/means[0][basis],
              "auto_unspecified_ci95": list(boot_ratio_ci([pricing.log_cost(r, basis) for r in groups[-1]], [pricing.log_cost(r, basis) for r in groups[None]]))} for basis in ("actual", "legacy")}
    active = [r for r in sweep if r["thoughts"] > 0]
    flores, _ = measure()

    from demo import compare_personas as persona
    m = pricing.get("sonnet")
    personas = {}
    for legacy in (False, True):
        a = persona.simulate("A", persona.A_SYS, persona.A_USERS, persona.A_OUTPUTS, persona.A_THINK, effort=1,
                             ko_thinking=True, cache_ok=False, m=m, legacy=legacy)
        b = persona.simulate("B", persona.B_SYS, [persona.B_USER1, persona.B_USER2], persona.B_OUTPUTS, persona.B_THINK,
                             effort=persona.EFFORT_LOW, ko_thinking=False, cache_ok=True, m=m, legacy=legacy)
        personas["legacy" if legacy else "current"] = {"a_usd": a["cost"], "b_usd": b["cost"], "ratio": a["cost"]/b["cost"]}
    from experiments.exp04_agent_loop_sdd import sdd_scenarios
    sdd = {}
    for warm in (False, True):
        rows = sdd_scenarios(m, warm_cache=warm)
        sdd["legacy_warm" if warm else "cold"] = {"rows": rows, "saving_pct": (1-rows[-1]["total_usd"]/rows[0]["total_usd"])*100}
    from experiments.exp03_prompt_caching import session_cost
    cache_plain = session_cost(m, 20000, 1000, 1500, 100, cached=False)
    cache_full = session_cost(m, 20000, 1000, 1500, 100)
    cache_miss = session_cost(m, 20000, 1000, 1500, 100, hit_rate=0)
    def prefix_cost(prefix, cached):
        return session_cost(m, prefix, 0, 0, 100, cached=cached)
    from experiments.exp11_tool_output_bloat import simulate, scenario_cost
    tool = {}
    for strategy in ("naive", "compact", "subagent"):
        counts = simulate(20, 8000, 5000, 300, strategy)
        tool[strategy] = {**counts, "whole_system_usd": scenario_cost(m, counts)}
    from demo.vibe_vs_spec.sensitivity import calculate as case_calculate
    source_files = ["results/live_lang_thinking.jsonl", "results/thinking_sweep.jsonl",
                    "data/flores200/eng_Latn.devtest", "data/flores200/kor_Hang.devtest",
                    "demo/vibe_vs_spec/usage.json"]
    return {"schema_version": 1, "recomputed_on": "2026-09-20", "new_paid_api_calls": 0,
            "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_files},
            "flores": flores, "language": lang,
            "thinking_sweep": {"rows": sweep_rows, "ratios": ratios,
              "thought_share_aggregate": sum(r["thoughts"] for r in active)/sum(r["thoughts"]+r["cands"] for r in active)},
            "scenarios": {"personas": personas, "sdd": sdd,
              "cache": {"no_cache_usd": cache_plain, "cache_usd": cache_full, "all_miss_usd": cache_miss,
                        "saving_pct": (1-cache_full/cache_plain)*100},
              "compression_cache": {"plain": prefix_cost(12000, False), "compressed": prefix_cost(6000, False),
                                    "cached": prefix_cost(12000, True), "both": prefix_cost(6000, True)},
              "stack_saving_pct": (1 - .7*.6*.5*.75*.9)*100, "tool_bloat": tool},
            "estimated_case_price_sensitivity": case_calculate()}


def save(path=ROOT / "results/audit_metrics.json"):
    data = build()
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return data
