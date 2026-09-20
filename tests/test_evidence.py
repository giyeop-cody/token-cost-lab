import hashlib
import json
import math
from pathlib import Path

import pytest
from scipy.stats import norm, ttest_ind

from lab import pricing
from tools.stats_test import welch_details
from tools.thinking_sweep import n_correct, numeric_answer, wilson
from tools.verify_deck import same_value
from tools.render_reports import live_report, corrections_report

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("relative", ["results/live_lang_thinking.jsonl", "results/thinking_sweep.jsonl",
                                     "data/flores200/eng_Latn.devtest", "data/flores200/kor_Hang.devtest"])
def test_immutable_primary_sources(relative):
    manifest = json.loads((ROOT / "data/evidence_manifest.json").read_text())["files"][relative]
    raw = (ROOT / relative).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["sha256"]
    assert len(raw.splitlines()) == manifest["rows"]


def test_published_metrics_match_primary_sources(evidence):
    assert same_value(evidence, json.loads((ROOT / "results/audit_metrics.json").read_text()))
    assert evidence["new_paid_api_calls"] == 0


def test_new_parallel_corpus_measurement(evidence):
    f = evidence["flores"]
    assert f["n_pairs"] == 1012
    assert f["chars"] == {"en": 131966, "ko": 65965}
    for name, en, ko in (("o200k_base", 26873, 39566), ("cl100k_base", 27182, 64338)):
        got = f["tokenizers"][name]
        assert (got["en"], got["ko"]) == (en, ko)
        assert got["ko_en_ratio"] == pytest.approx(ko/en)
    rows = [json.loads(s) for s in (ROOT / "results/flores_tokenizers.jsonl").read_text().splitlines()]
    assert len(rows) == 1012
    assert sum(r["o200k_base"]["ko"] for r in rows) == 39566


@pytest.mark.parametrize("task", ["explain", "reason"])
@pytest.mark.parametrize("metric", ["per_call", "per_1000_chars"])
@pytest.mark.parametrize("basis", ["actual", "legacy"])
def test_welch_matches_scipy_not_normal_tail(task, metric, basis):
    rows = [json.loads(s) for s in (ROOT / "results/live_lang_thinking.jsonl").read_text().splitlines()]
    groups = {language: [pricing.log_cost(r, basis) * (1000/r["chars"] if metric == "per_1000_chars" else 1)
                        for r in rows if r["task"] == task and r["lang"] == language] for language in ("ko", "en")}
    a, b = groups["ko"], groups["en"]
    t, p, df = welch_details(a, b)
    reference = ttest_ind(a, b, equal_var=False)
    assert t == pytest.approx(reference.statistic, rel=1e-12)
    assert p == pytest.approx(reference.pvalue, rel=1e-11)
    assert df == pytest.approx(reference.df, rel=1e-12)
    assert p > 2*norm.sf(abs(t))
    assert p*4 < .05


@pytest.mark.parametrize("a,b", [([1],[2,3]), ([1,1],[2,2]), ([],[])])
def test_unestimable_welch_is_not_significant(a, b):
    assert all(math.isnan(x) for x in welch_details(a, b))


def test_preserve_two_price_bases_and_distinct_reference_settings(evidence):
    sw = evidence["thinking_sweep"]
    assert sw["ratios"]["actual"]["auto_unspecified"] == pytest.approx(199.47321428571428)
    assert sw["ratios"]["legacy"]["auto_unspecified"] == pytest.approx(240.0215053763441)
    assert sw["ratios"]["actual"]["auto_zero"] == pytest.approx(195.97368421052633)
    assert [r["n"] for r in sw["rows"]] == [6]*5
    assert [r["pass_tolerance_0_05"] for r in sw["rows"]] == [6,5,2,6,6]
    assert [r["exact_1e_9"] for r in sw["rows"]] == [6,5,1,4,3]
    assert sw["rows"][2]["thoughts_max"] < 512
    raw = [json.loads(x) for x in (ROOT / "results/thinking_sweep.jsonl").read_text().splitlines()]
    active = [r for r in raw if r["thoughts"] > 0]
    thought = sum(r["thoughts"] for r in active)
    visible = sum(r["cands"] for r in active)
    assert sw["thought_share_aggregate"] == pytest.approx(thought/(thought+visible), rel=1e-14)


@pytest.mark.parametrize("text,tolerant,exact", [("$38.016",True,True), ("37.9944",True,False),
                                               ("380.16",False,False), ("5 calls then 38.016",False,False)])
def test_answer_scoring_does_not_confuse_tolerance_and_exact(text, tolerant, exact):
    assert bool(n_correct([{"text": text}])) == tolerant
    assert bool(n_correct([{"text": text}], 1e-9)) == exact


def test_tiny_sample_wilson_interval():
    lo, hi = wilson(6,6)
    assert lo == pytest.approx(.60966, abs=1e-4)
    assert hi == pytest.approx(1)
    assert wilson(0,0) == (0,1)


def test_scenario_numbers_remain_scenarios(evidence):
    s = evidence["scenarios"]
    assert s["personas"]["legacy"]["ratio"] == pytest.approx(20.81879117765577)
    assert s["personas"]["current"]["ratio"] == pytest.approx(18.963528611028466)
    assert s["sdd"]["cold"]["saving_pct"] == pytest.approx((1-.591/1.89)*100)
    assert s["sdd"]["legacy_warm"]["saving_pct"] == pytest.approx((1-.5082/1.752)*100)
    assert s["stack_saving_pct"] == pytest.approx(85.825)
    assert not 60 <= s["stack_saving_pct"] <= 80
    assert s["compression_cache"] == pytest.approx(dict(plain=3.6, compressed=1.8, cached=.4014, both=.2007))


def test_reports_are_generated_from_same_evidence(evidence):
    assert (ROOT / "LIVE_RESULTS.md").read_text() == live_report(evidence)
    assert (ROOT / "docs/CORRECTIONS.md").read_text() == corrections_report(evidence)


def test_case_estimates_and_no_cache_alternative(evidence):
    case=evidence["estimated_case_price_sensitivity"]
    assert case["delta_tokens"] == dict(uncached_input=666,cached_input=156,reasoning_plus_output=-680)
    g=case["models"]["gpt5"]
    assert (g["vibe_usd"],g["spec_usd"]) == pytest.approx((.0713465,.0653985))
    assert (g["no_cache_vibe_usd"],g["no_cache_spec_usd"]) == pytest.approx((.0716975,.065925))
    s=case["models"]["sonnet"]
    assert (s["vibe_usd"],s["spec_usd"]) == pytest.approx((.1076016,.0994464))
    for relative in ("demo/vibe_vs_spec/README.md","presentation/case_vibe_vs_spec/cost_comparison.md"):
        text=(ROOT/relative).read_text()
        for value in (s["vibe_usd"],s["spec_usd"]): assert f"${value:.7f}" in text
    assert (g["spec_usd"]-g["vibe_usd"]) == pytest.approx(1.25/1e6*(666+156*.1-680*8))
