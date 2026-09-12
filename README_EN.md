# token-cost-lab

**A lab of hands-on experiments that re-measures LLM token-cost reduction — your own numbers, not blog posts.**

Companion repository for the talk *"How to reliably cut your token usage."*
Every number in the talk is reproducible with the scripts in this repo.

```bash
git clone <this-repo> && cd token-cost-lab
pip install -r requirements.txt
python run_all.py
```

No API key needed. It runs on measured tokenizer counts + public-price simulation.

> This document is English · [한국어 (Korean)](README.md)

---

## Why this exists

There are many "save tokens" blog posts, and most of them end with a one-liner:
*"Use prompt caching and you'll save 90%."*

The problem: nobody says **at what prefix length, over how many calls, at what
hit rate** that 90% was measured. Change the parameters and "90% savings"
can flip into an 18% loss (Section E of experiment 03 is exactly that case).

This repo **exposes every assumption as a command-line argument**.
Plug in your team's real numbers and re-run.

---

## Experiments

| # | File | What it measures | Evidence |
|---|---|---|---|
| 01 | `exp01_tokenizer_ko_en.py` | Korean/English token multiplier (tiktoken, measured) | [Petrov+ NeurIPS'23](https://arxiv.org/abs/2305.15425) |
| 02 | `exp02_output_to_input.py` | Output→input arbitrage, break-even | Vendor [price lists](#4-price-pages) |
| 03 | `exp03_prompt_caching.py` | Caching savings curve, cache-invalidation cost | [Anthropic](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) · [OpenAI](https://platform.openai.com/docs/guides/prompt-caching) · [Lost in the Middle](https://arxiv.org/abs/2307.03172) |
| 04 | `exp04_agent_loop_sdd.py` | Quadratic loop cost, SDD, YAGNI | [Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| 05 | `exp05_verbosity_effort.py` | Verbosity, reasoning effort, tool schemas | [XReasoning](https://arxiv.org/abs/2505.22888) · vendor docs |
| 06 | `exp06_other_levers.py` | Batch · compression · semantic cache · routing · layering | [RouteLLM](https://arxiv.org/abs/2406.18665) · [LLMLingua](https://arxiv.org/abs/2310.05736) · [GPT Semantic Cache](https://arxiv.org/abs/2411.05276) |
| 07 | `exp07_analyze_my_prompt.py` | **Diagnose your own prompt file** | [Lost in the Middle](https://arxiv.org/abs/2307.03172) |
| 08 | `exp08_gemini_live.py` | **Live Gemini API calls → real billed tokens** | [Gemini token docs](https://ai.google.dev/gemini-api/docs/tokens) |
| 10 | `exp10_thinking_cross_vendor.py` | Thinking tokens & billing **across 3 vendors** (Gemini/Anthropic/OpenAI) | [Anthropic extended thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) · [OpenAI reasoning](https://platform.openai.com/docs/guides/reasoning) |
| 11 | `exp11_tool_output_bloat.py` | **Tool-output context bloat** (simulation + live function calling) | [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling) |

Exact citation info for every item is in **[SOURCES.md](SOURCES.md)**.

Real-world case study: **[demo/vibe_vs_spec/](demo/vibe_vs_spec/)** — the same page built from
a free-form prompt (Vibe) vs. a deterministic spec (Spec), compared by tokens and cost.
A short 4-field spec: tokens +1.8% but cost −8.3%, supporting experiment 04's (SDD)
falsification section's conclusion ("use short, decisions-only specs").

### Running individually

```bash
python experiments/exp01_tokenizer_ko_en.py
python experiments/exp02_output_to_input.py --model opus --devs 25
python experiments/exp03_prompt_caching.py --static 40000 --calls 500
python experiments/exp04_agent_loop_sdd.py --turns 40
python experiments/exp05_verbosity_effort.py --calls 5000
python experiments/exp06_other_levers.py --calls 100000
python experiments/exp08_gemini_live.py --dry-run       # structure only (no key)
python experiments/exp08_gemini_live.py --list-models    # check available models (no billing)
python experiments/exp10_thinking_cross_vendor.py --dry-run  # 3-vendor structure (no key)
python experiments/exp11_tool_output_bloat.py --turns 40 --tool-tokens 20000
```

### #07 is especially practical

Point it at your system prompt and it flags what's breaking your cache.

```bash
python experiments/exp07_analyze_my_prompt.py my_system_prompt.md
python experiments/exp07_analyze_my_prompt.py --demo     # see the example first
cat CLAUDE.md | python experiments/exp07_analyze_my_prompt.py -
```

Sample output:

```
── 3. Cache-breaking elements — dynamic values near the top
  position   doc position  kind           value
  🔴 top      7%           timestamp       2026-08-14 09:31
  🔴 top      12%           request/session id  req_8f3a21c9
  🔴 5 dynamic values in the front 1/3. Cache hit rate goes to ~0.
```

### #08 is the only one that shows you the "real invoice"

> **Live measurement complete (2026-08-15)**: actual call results are in
> **[LIVE_RESULTS.md](LIVE_RESULTS.md)**.
> Highlight — same question, only the thinking budget changed: the visible
> answer was 4–5 tokens in every case, but the **cost differed 37×**.
> The entire difference is `thoughtsTokenCount` — tokens you never see.
>
> ⚠️ `gemini-2.5-*` returns 404 for new API keys. Use `--list-models` first.

01–07 and 09 are all simulation. **08 (Gemini), 10 (Gemini/Anthropic/OpenAI) and
11-B (function calling) actually call the API** and read the real token counts
from `usageMetadata`/`usage`. (Without keys they fall back to dry-run/simulation.)

```bash
export GEMINI_API_KEY="..."        # https://aistudio.google.com/apikey (free tier available)

python experiments/exp08_gemini_live.py --dry-run     # structure only, no billing
python experiments/exp08_gemini_live.py --count-only  # input tokens only, no billing
python experiments/exp08_gemini_live.py               # KR/EN live comparison
python experiments/exp08_gemini_live.py --thinking    # tokens by thinking budget
python experiments/exp08_gemini_live.py --prompt "$(cat my_prompt.md)"
```

For a live talk demo, `--thinking` lands best: ask the same question three times,
varying only the thinking budget, and the table shows **invisible thinking tokens
billed at the output rate**.

```
  thinking budget  think tok  resp tok  out total  cost
  ---------------  ---------  --------  ---------  ---------
  off (0)                 0        30        30    $0.000355
  cap 512                480        30       510   $0.005155
  auto (-1)              640        30       670   $0.006755
```

**Two classic metering mistakes:**

1. `promptTokenCount` **already includes** cached tokens.
   Billed input = `promptTokenCount − cachedContentTokenCount`.
   Skip this and caching savings never show up in your ledger.
2. In streaming, `usageMetadata` arrives as a **cumulative value per chunk**.
   Don't sum them — use the **last chunk's value only**. (Some SDKs send
   `cachedContentTokenCount` as `undefined`, not 0.)

---

## The talk's core claims and how they held up

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| ① | Reason in English | **True**, but the multiplier differs per model | KR 1.44× on o200k, 2.22× on cl100k (exp01) · [Petrov+ 2023](https://arxiv.org/abs/2305.15425) |
| ② | Follow KISS/DRY/YAGNI | **True**, but the driver is turn count, not unit price | Unused code is re-sent every turn (exp04-D) |
| ③ | Ban verbose explanations | **True** | Cutting prose alone: output −40~60% (exp05-A) |
| ④ | Reason on the web, inject the result | **True** (= SDD) | 71% per-feature savings from fewer turns (exp04-B) · [Anthropic 2025](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| ⑤ | Converting output into input is the lever | **True** | Input 3× higher, total cost 66% lower (exp02-B) |

### We ship the counter-evidence too

This repo doesn't just collect confirming evidence. Contradicting findings are
printed alongside, marked `⚠️`, inside the experiment scripts.

- **English reasoning isn't always cheaper** — Qwen3 has been reported to use 40%
  fewer tokens with Chinese CoT than English.
- **Forcing user-language thinking hurts accuracy** — in XReasoning (arXiv:2505.22888),
  language match rose 46%→98% but accuracy dropped 26%→17%.
- **Specs aren't always a win** — an ETH Zurich study ([SOURCES.md §4](SOURCES.md#4-counter-evidence--limiting-materials))
  found LLM-generated context files slightly *lower* success rates while raising
  reasoning cost 20%+. One benchmark had Spec-Kit use up to 2× the tokens of OpenSpec.
  → The conclusion is not "use specs" but **"use short, decisions-only specs."**
- **Caching loses money when misused** — a dynamic value in front of your prefix
  charges the write premium every time and ends 18% *more* expensive than no cache (exp03-E).

---

## What you can do today (prioritized)

| Rank | Lever | Effort | Risk | Apply when |
|---|---|---|---|---|
| 1 | Prompt caching | Low | None | Fixed prefix ≥1K tokens |
| 2 | Verbosity / reasoning effort | Low | Low | Usually a one-line setting |
| 3 | Batch API (50% off) | Low | None | You have latency-tolerant jobs |
| 4 | Specs first (SDD) | Medium | Low | Rework cycles ≥3 |
| 5 | Context compaction | Medium | Medium | Sessions past 20 turns |
| 6 | Model routing | High | Medium | You have quality measurement |
| 7 | Semantic caching | High | High | Query repetition ≥20% |
| 8 | Prompt compression | High | Medium | RAG context ≥10K tokens |

Items 1–3 can be switched on and back off in an afternoon. 6–8 need a quality
measurement system first.

---

## Price information refresh

All unit prices live in **one place: `lab/pricing.py`**. Based on the 2026-08
public lists (some models added 2026-09-11). Prices change often — re-check the
official pages before any talk or report, then update:

- [Anthropic](https://www.anthropic.com/pricing) ·
  [OpenAI](https://openai.com/api/pricing) ·
  [Google Gemini](https://ai.google.dev/pricing) ·
  [DeepSeek](https://api-docs.deepseek.com/quick_start/pricing)

```python
MODELS = {
    "sonnet": Model("Claude Sonnet 4.6", 3.00, 15.00, 0.10, 1.25),
    #                                  input  output  cache_read  cache_write
}
```

Add a model and every experiment accepts it via `--model <key>`.

---

## What this repo does NOT do

Stated plainly.

- **exp01–07, 09 and exp11-A do not call real APIs.** Token counts are measured
  with tiktoken, but costs are simulations on public prices. Per-workflow token
  numbers (e.g. "a vague instruction produces 12,000 output tokens") are typical
  assumptions, not measurements. For real billed values use **exp08** (Gemini),
  **exp10** (3 vendors), **exp11-B** (function calling). Note: a single live call
  is one sample — repeat it and talk about averages.
- **exp10 and 11-B were added 2026-09.** They have no finalized LIVE_RESULTS yet —
  they produce numbers only in an environment with API keys + billing. exp10 is
  n=1 per condition: treat it as a reproducible scaffold, not a conclusion.
- **We don't measure quality.** Only cost. Lowering effort or compressing harder
  can reduce accuracy, and that loss is invisible here.
- **We don't use the Anthropic tokenizer directly.** No public library exists, so
  we approximate with tiktoken. External corpus measurements put the Claude
  tokenizer's Korean multiplier at 1.88 — worse than o200k. So this repo's Korean
  cost estimates are on the **conservative** side.

The most accurate method is always **your own account's usage logs**.
This repo tells you where to look first, before you read those logs.

---

## Requirements

- Python 3.9+
- `tiktoken` (the only hard dependency)

```bash
pip install -r requirements.txt
```

## Layout

```
token-cost-lab/
├── README.md
├── README_EN.md                 # this file
├── SOURCES.md                   # original links for every cited source
├── LIVE_RESULTS.md              # live-measurement record (2026-08-15)
├── requirements.txt
├── LICENSE                      # MIT
├── run_all.py                   # runs exp01~11 (no billing)
├── .github/workflows/ci.yml     # CI: all experiments + number regression check
├── lab/
│   ├── pricing.py               # price table (edit this one file only)
│   └── report.py                # console table output (Korean width handling)
├── data/
│   └── sentence_pairs.json      # 6 identical-meaning Korean/English sentence pairs
├── experiments/
│   ├── exp01_tokenizer_ko_en.py   ~ exp07_analyze_my_prompt.py
│   ├── exp08_gemini_live.py       # real API calls (only with a key)
│   ├── exp09_dry.py               # the token economics of DRY
│   ├── exp10_thinking_cross_vendor.py  # thinking tokens across 3 vendors
│   └── exp11_tool_output_bloat.py      # tool-output context bloat
├── tools/
│   ├── live_lang_bench.py       # KR/EN × explain/reason live benchmark
│   ├── stats_test.py            # bootstrap CI · Welch · Cliff's δ
│   ├── thinking_sweep.py        # thinking-budget sweep (+ Wilson CI · price sensitivity)
│   └── verify_deck.py           # slide-number regression check
├── results/                     # raw measurement data (verifiable without re-running)
│   ├── live_lang_thinking.jsonl   # 80 rows
│   ├── thinking_sweep.jsonl       # 30 rows
│   └── stats_thinking.txt · sweep_summary.txt
└── demo/                        # persona A/B token comparison
    ├── compare_personas.py      # 4-axis live comparison: input/output/thinking/caching
    ├── memo.html                # identical deliverable made by both personas
    ├── 비교.html                 # results visualization
    ├── qr_repo.png
    └── transcripts/             # full conversation logs (token metering source)
```

### What is NOT in this repo

The presentation deliverables (`토큰_절약_발표.pptx` / `.pdf`, talk script,
verification report) live on the **`presentation` branch**, not here.
The repo holds *only the code that reproduces the numbers*.

So `tools/verify_deck.py` **SKIPs** the deck checks when no deck file exists and
runs the other 87 checks. A plain clone still works normally.

```bash
git checkout presentation     # 29-slide deck · PDF · talk script · build tools
python tools/verify_deck.py   # main: 87 checks pass · presentation: 98 checks
```

## Contributing

PRs welcome: extend `data/sentence_pairs.json` with your team's measured pairs,
or add models to `lab/pricing.py`.
When citing external numbers, always include the source — original title, author,
link — in **[SOURCES.md](SOURCES.md)**, plus a link in the `출처:` (Sources:) block at
the bottom of the relevant experiment's docstring.

## License

MIT
