# token-cost-lab

**Reproducible LLM cost experiments, with measurements separated from assumptions.**

[한국어](README.md) · [Observed logs and local measurements](LIVE_RESULTS.md) · [Correction report](docs/CORRECTIONS.md) · [Sources](SOURCES.md)

## The practical claims remain

Use English where it improves token efficiency or reasoning accuracy; reduce needless
code, explanations, reasoning and rework; specify decisions up front; and apply
caching/context management/routing where suitable. Measure quality and total cost.
These are conditional recommendations, not universal savings guarantees.


Initial dependencies, browser binaries and tiktoken encoding files may need downloading; no paid LLM API is involved.

## September 20, 2026 corrections

| Evidence | Result | Scope |
|---|---|---|
| New local measurement | 1,012 FLORES-200 aligned pairs: KO/EN **1.4723×** (`o200k_base`), **2.3669×** (`cl100k_base`) | Encoding, not Gemini/Claude generation or accuracy |
| Existing API logs recalculated | Automatic/unspecified: **199.47×** at the actual model's Standard rate; **240.02×** at the legacy talk conversion | One arithmetic question, six repeats/condition |
| Scoring | Unspecified 6/6, explicit zero 5/6, automatic 6/6 within ±$0.05 | Exact numeric scoring is 6/6, 5/6, 3/6 respectively; no equivalence claim |
| Statistics | Reason task per-character p: **6.08e-10 → 4.02e-7** | Legacy rate held fixed; Welch t distribution replaces normal approximation |
| External accuracy research | Korean MATH-500: **83.7% / 75.4%** for English/target-language prefilling | *Language Matters*, Table 1, four-model average; not rerun here |
| Cost scenarios | Legacy persona **20.8×** and prewarmed SDD **~71%** retained as assumptions | Corrected defaults: **19.0× / 68.7%**; not quality-matched policy A/B |

**Zero new paid model calls were made for this correction.** The original 110 stored
API usage rows remain unchanged. A shorter Korean answer is not necessarily less
meaning; more hidden reasoning tokens do not establish deeper or better reasoning.
Per-call and per-character costs answer different questions.

## Run offline (Python 3.10+)

```bash
pip install -r requirements.txt
python run_all.py
python tools/parallel_tokenizer_bench.py
python tools/stats_test.py results/live_lang_thinking.jsonl
python tools/stats_test.py results/live_lang_thinking.jsonl --price-basis legacy
python tools/thinking_sweep.py --summarize results/thinking_sweep.jsonl
python demo/compare_personas.py
python demo/compare_personas.py --scenario legacy
```

`exp01` measures six local text pairs; the FLORES tool measures 1,012 pairs.
`exp02`–`exp07` and `exp09` combine local encodings, heuristics and cost assumptions.
`exp08`, `exp10` and `exp11 --live` can make paid API calls when explicitly requested.
`run_all.py` is offline unless `--live` is supplied. Missing keys, truncation and
request failures must not produce a prewritten “verified” conclusion.

## Reproduction and validation

```bash
pip install -r requirements-dev.txt
python -m playwright install --with-deps chromium
python tools/reproduce_audit.py
python -m pytest -q
python demo/vibe_vs_spec/verify_ac.py
python tools/verify_deck.py --with-pdf
```

LibreOffice and Nanum fonts are required to regenerate PDFs:
`python presentation/deckgen/make_pdf.py --check`.
The complete local gate is `python tools/check_audit.py`, recording actual exit codes
and test counts in `results/verification.json`. A workflow has been added; local
success is not a claim that GitHub Actions has already run.
All five decks and scripts use one source of truth. Validators compare actual
PPTX/PDF text, not only internal constants. Mutation tests reject changed slide
numbers, two-column mobile layouts and nonfunctional memo HTML.

`lab/pricing.py` separates model-ID-specific snapshots, legacy talk conversion
and hypothetical router tiers. See [pricing scope](docs/PRICING.md).
Gemini prompt counts already include cached input: subtract it exactly once,
charge the cache bucket at its own rate, and add visible + thinking output.
Cache eligibility is model-specific (Haiku 4.5: 4,096 tokens).

## Limits

No new multilingual accuracy benchmark, randomized policy A/B, invoice comparison,
quality-equivalence study, IDE GUI or physical presentation-device test was run.
Mocks validate contracts/accounting, not model outcomes. The cafe case uses estimated
usage. Persona transcripts and replay figures are scenarios, not measured policy effects.
Missing pilot raw data was not fabricated. Historical drafts are explicitly superseded
in `docs/archive/` and `presentation/archive/`.

API price estimates exclude contractual/free-tier effects, tax, subscriptions,
long-context premiums and separate tool/storage charges unless stated otherwise.
FLORES data has its own CC-BY-SA 4.0 attribution; repository code is MIT.
