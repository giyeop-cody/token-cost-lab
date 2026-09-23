#!/usr/bin/env python3
"""발표용 그래프 생성기 — 단가·사용량 비교 차트.

원칙:
  · 차트에 그려지는 모든 수치는 `lab/pricing.py` · `lab/evidence.py` · 저장 자료에서 계산한다.
    손으로 적은 숫자를 그리지 않는다.
  · 같은 입력이면 같은 파일이 나온다(고정 figsize/dpi/색·글꼴). 그래서 덱·PDF와 바이트 대조가 가능하다.
  · `charts/manifest.json`에 각 차트의 계열값과 파일 해시를 기록한다. 테스트가 이 둘을 다시 대조한다.

필요 환경: matplotlib, NanumGothic(없으면 UNVERIFIED로 종료).

실행:
  python presentation/deckgen/make_charts.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BG, FG, MUTED, ACC, ACC2, GRID = "#0E141B", "#ECF1F6", "#93A4B5", "#36D399", "#6EA8FE", "#22303D"
FONT = "NanumGothic"
FIGSIZE = (12.6, 4.34)    # 슬라이드 상자(11.65 x 3.95 in)를 꽉 채우는 종횡비
DPI = 200

PRICE_ROWS = ("opus", "sonnet", "gpt5", "gemini-pro", "flash-lite", "deepseek")
SHORT = {"opus": "Opus 4.6", "sonnet": "Sonnet 4.6", "gpt5": "GPT-5",
         "gemini-pro": "Gemini 3.1 Pro", "flash-lite": "Flash-Lite", "deepseek": "DeepSeek (peak)"}
# 차트 축 라벨은 잘리지 않도록 짧게 쓴다(정식 이름은 manifest와 슬라이드에 있다).
SHORT_AXIS = {"opus": "Opus", "sonnet": "Sonnet", "gpt5": "GPT-5",
              "gemini-pro": "Gemini Pro", "flash-lite": "Flash-Lite", "deepseek": "DeepSeek"}


def _load():
    """차트에 쓰는 계열값을 모두 계산한다(이 함수의 출력이 manifest의 단일 원천)."""
    from lab import pricing
    from lab.evidence import build
    from experiments.exp04_agent_loop_sdd import compacted_loop, naive_loop

    e = build()
    m = pricing.get("sonnet")
    base, turn_in, turn_out = 8_000, 2_000, 800

    turn_rows = {}
    for n in (5, 10, 20, 30, 50):
        cost, tokens_in = naive_loop(m, n, base, turn_in, turn_out)
        turn_rows[str(n)] = {"cost_usd": round(cost, 6), "cumulative_input_tokens": tokens_in}
    compaction = {}
    for every in (10, 5):
        cost, _ = compacted_loop(m, 20, base, turn_in, turn_out, every=every)
        compaction[str(every)] = round(cost, 6)

    layers = [("시맨틱 캐싱", 0.30), ("모델 라우팅", 0.40), ("프롬프트 캐싱", 0.50),
              ("verbosity·effort", 0.25), ("배치", 0.10)]
    remaining, stack = 1.0, []
    for label, cut in layers:
        before = remaining
        remaining *= (1 - cut)
        stack.append({"lever": label, "cut_pct": cut * 100, "remaining_before_pct": before * 100,
                      "remaining_after_pct": remaining * 100})

    sweep = {r["label"]: r["cost_per_call"]["actual"] for r in e["thinking_sweep"]["rows"]}

    case = json.loads((ROOT / "demo/vibe_vs_spec/usage.json").read_text(encoding="utf-8"))["runs"]
    case_tokens = {mode: {"uncached_input": case[mode]["tokens"]["input"],
                          "reasoning_plus_output": case[mode]["tokens"]["reasoning"] + case[mode]["tokens"]["output"],
                          "cached": case[mode]["tokens"]["cache"]} for mode in ("vibe", "spec")}
    sens = e["estimated_case_price_sensitivity"]["models"]
    case_bases = {key: {"name": sens[key]["model"], "vibe_usd": sens[key]["vibe_usd"],
                        "spec_usd": sens[key]["spec_usd"], "delta_pct": sens[key]["delta_pct"]}
                  for key in ("gpt5", "sonnet", "opus")}
    case_bases["gpt5_no_cache"] = {"name": "GPT-5 (캐시 미적용)", "vibe_usd": sens["gpt5"]["no_cache_vibe_usd"],
                                  "spec_usd": sens["gpt5"]["no_cache_spec_usd"],
                                  "delta_pct": sens["gpt5"]["no_cache_delta_pct"]}

    fl = e["flores"]["tokenizers"]
    from experiments.exp01_tokenizer_ko_en import load_pairs
    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")
    pairs = load_pairs(ROOT / "data/sentence_pairs.json")
    en_text, ko_text = " ".join(p["en"] for p in pairs), " ".join(p["ko"] for p in pairs)
    tpc = {"en": round(len(enc.encode(en_text)) / len(en_text), 4),
           "ko": round(len(enc.encode(ko_text)) / len(ko_text), 4)}

    # 월 청구서(모델별) — 워크플로 A/B, 월 1,760건
    from lab.pricing import cost as price_cost
    jobs_per_month = 1_760
    workflows = {"A": (2_000, 12_000), "B": (6_000, 3_000)}
    monthly = {}
    for key in PRICE_ROWS:
        model = pricing.MODELS[key]
        monthly[SHORT_AXIS[key]] = {w: round(price_cost(model, *workflows[w]) * jobs_per_month, 2)
                                    for w in workflows}

    # 캐시 적중률 곡선 — 캐시 없음 / 적중률별 / 전부 미스
    from experiments.exp03_prompt_caching import session_cost
    m_sonnet = pricing.get("sonnet")
    hit = {f"{h:.2f}": round(session_cost(m_sonnet, 20_000, 1_000, 1_500, 100, hit_rate=h), 4)
           for h in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)}
    no_cache = round(session_cost(m_sonnet, 20_000, 1_000, 1_500, 100, cached=False), 4)
    breakeven = round((hit["0.00"] - no_cache) / (hit["0.00"] - hit["1.00"]), 4)

    # 사용량 구성 — 20턴 세션의 입력/출력 토큰 비중
    turns_n, tokens_in = 20, turn_rows["20"]["cumulative_input_tokens"]
    fixed_resent = base * turns_n
    history_resent = tokens_in - fixed_resent
    output_tokens = turn_out * turns_n
    usage_mix = {"고정 프리픽스 재전송": fixed_resent, "대화 이력 재전송": history_resent,
                 "출력(생성)": output_tokens}
    usage_total = sum(usage_mix.values())

    return {
        "monthly": {
            "unit": "USD / month", "caption_ko": "월 청구서 (USD)",
            "jobs_per_month": jobs_per_month,
            "workflows": {"A": "입력 2,000 · 출력 12,000", "B": "입력 6,000 · 출력 3,000"},
            "by_model": monthly,
        },
        "cache_hit": {
            "unit": "USD / 100 calls", "caption_ko": "적중률별 비용 (USD)",
            "no_cache_usd": no_cache, "by_hit_rate": hit, "breakeven_hit_rate": breakeven,
        },
        "usage_mix": {
            "unit": "tokens", "caption_ko": "20턴 세션 토큰 구성", "turns": turns_n,
            "parts": usage_mix, "total": usage_total,
            "shares_pct": {k: round(v / usage_total * 100, 2) for k, v in usage_mix.items()},
        },
        "prices": {
            "unit": "USD / 1M tokens", "caption_ko": "단가 스냅샷 (USD / 100만 토큰)",
            "labels": [SHORT[k] for k in PRICE_ROWS],
            "axis_labels": [SHORT_AXIS[k] for k in PRICE_ROWS],
            "input": [pricing.MODELS[k].inp for k in PRICE_ROWS],
            "output": [pricing.MODELS[k].out for k in PRICE_ROWS],
            "output_to_input": [round(pricing.MODELS[k].ratio, 3) for k in PRICE_ROWS],
            "cache_read_multiple": [pricing.MODELS[k].cache_read for k in PRICE_ROWS],
        },
        "tokenizer": {
            "unit": "tokens", "caption_ko": "토크나이저 실측 (토큰)",
            "flores_pairs": e["flores"]["n_pairs"],
            "ko_en_ratio": {k: round(v["ko_en_ratio"], 4) for k, v in fl.items()},
            "tokens_per_char": tpc,
            "tokens_per_char_corpus": "data/sentence_pairs.json (o200k_base)",
        },
        "cache": {
            "unit": "USD / 100 calls", "caption_ko": "100콜 비용 (USD)",
            "labels": ["캐시 없음", "캐시 100% 적중", "미스 배치(0% 적중)"],
            "values": [e["scenarios"]["cache"]["no_cache_usd"], e["scenarios"]["cache"]["cache_usd"],
                       e["scenarios"]["cache"]["all_miss_usd"]],
        },
        "turns": {
            "unit": "USD / session", "caption_ko": "세션 비용 (USD)",
            "model": m.name, "base_tokens": base, "turn_input": turn_in, "turn_output": turn_out,
            "turns": turn_rows,
            "compaction_20_turns": compaction,
        },
        "stack": {"unit": "% of baseline", "caption_ko": "남은 비율 (%)", "layers": stack, "remaining_pct": remaining * 100},
        "thinking": {"unit": "USD / call (actual price basis)", "caption_ko": "호출당 비용 (USD)", "by_budget": sweep},
        "case_tokens": {"unit": "tokens", "caption_ko": "토큰 수 (추정)", "modes": case_tokens},
        "case_bases": {"unit": "USD", "caption_ko": "추정 비용 (USD)", "bases": case_bases},
    }


def plt_patch(*args, **kwargs):
    from matplotlib.patches import Patch
    return Patch(*args, **kwargs)


def _axes(left=0.075, right=0.985, bottom=0.20, top=0.86):
    """단일 패널 발표용 차트. 큰 글자·어두운 배경·초록 강조."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    if FONT not in {f.name for f in font_manager.fontManager.ttflist}:
        raise SystemExit(f"UNVERIFIED: {FONT} 글꼴이 없습니다. 예: sudo apt-get install -y fonts-nanum")
    plt.rcParams.update({
        "font.family": FONT, "axes.unicode_minus": False, "figure.facecolor": BG, "axes.facecolor": BG,
        "text.color": FG, "axes.labelcolor": FG, "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.edgecolor": GRID, "savefig.facecolor": BG,
    })
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = fig.add_axes([left, bottom, right - left, top - bottom])
    return fig, ax


def _clean(ax, grid_axis="y", title=""):
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0, labelsize=14)
    ax.grid(axis=grid_axis, color=GRID, linewidth=.8)
    ax.set_axisbelow(True)
    ax.set_title(title, color=FG, fontsize=18.5, loc="left", pad=14)


def _two():
    fig, _ = _axes()
    import matplotlib.pyplot as plt
    plt.close(fig)
    from matplotlib import pyplot as plt2
    fig, axes = plt2.subplots(1, 2, figsize=FIGSIZE, dpi=DPI)
    fig.patch.set_facecolor(BG)
    return fig, list(axes)


def _close(fig, path):
    import matplotlib.pyplot as plt
    fig.savefig(path)
    plt.close(fig)


def _save(ax, fig, path):
    _close(fig, path)


def _label(ax, xs, values, fmt, color=ACC, size=13, weight="bold", inside_below=False):
    for x, value in zip(xs, values):
        offset = -14 if inside_below else 6
        ax.annotate(fmt.format(value), (x, value), textcoords="offset points", xytext=(0, offset),
                    ha="center", va="top" if inside_below else "bottom", color=color,
                    fontsize=size, fontweight=weight)


def draw_prices(data, path):
    import matplotlib.ticker as mticker
    fig, ax = _axes(left=0.125)
    labels = data["labels"]
    y = list(range(len(labels)))
    h = 0.36
    ax.barh([i + h / 2 + .02 for i in y], data["output"], height=h, color=ACC, label="출력")
    ax.barh([i - h / 2 - .02 for i in y], data["input"], height=h, color=ACC2, label="입력")
    ax.set_xscale("log")
    ax.set_xlim(0.11, 42)
    ax.set_xticks([0.1, 0.3, 1, 3, 10, 30], ["$0.1", "$0.3", "$1", "$3", "$10", "$30"])
    ax.xaxis.set_minor_formatter(mticker.NullFormatter())
    ax.set_yticks(y, data["axis_labels"], fontsize=15)
    ax.set_ylim(-0.7, len(labels) - 0.3)
    for i, (a, b) in enumerate(zip(data["input"], data["output"])):
        ax.annotate(f"${a:g}", (a, i - h / 2 - .02), textcoords="offset points", xytext=(6, 0),
                    va="center", color=ACC2, fontsize=12)
        ax.annotate(f"${b:g}", (b, i + h / 2 + .02), textcoords="offset points", xytext=(6, 0),
                    va="center", color=ACC, fontsize=12, fontweight="bold")
    ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=12, loc="upper right", framealpha=1)
    _clean(ax, "x", "모델별 입력·출력 단가 (USD / 100만 토큰, 로그 축)")
    _close(fig, path)


def draw_tokenizer(data, path):
    fig, ax = _axes(left=0.17)
    ratios = data["ko_en_ratio"]
    labels, values, colors = [], [], []
    for key, name in (("o200k_base", "o200k_base"), ("cl100k_base", "cl100k_base")):
        labels += [f"{name} · 영어", f"{name} · 한국어"]
        values += [1.0, ratios[key]]           # 영어를 1.0으로 두고 한국어 배수를 보여 준다
        colors += [ACC2, ACC]
    y = list(range(len(labels)))
    bars = ax.barh(y, values, color=colors, height=.52)
    ax.bar_label(bars, labels=[("1.00 (기준)" if v == 1.0 else f"{v:.4f}배") for v in values],
                 padding=8, color=FG, fontsize=14, fontweight="bold")
    ax.set_yticks(y, labels, fontsize=14)
    ax.set_xlim(0, max(values) * 1.28)
    ax.set_ylim(len(labels) - 0.4, -0.6)
    tpc = data["tokens_per_char"]
    ax.annotate(f"토큰/글자 · 영어 {tpc['en']:.3f} vs 한국어 {tpc['ko']:.3f} ({tpc['ko'] / tpc['en']:.2f}배)",
                (0.98, -0.45), xycoords=("axes fraction", "data"), ha="right", va="bottom",
                color=MUTED, fontsize=13)
    _clean(ax, "x", f"같은 내용(FLORES-200 {data['flores_pairs']:,}쌍)의 토큰 배수 — 영어 = 1.00")
    _close(fig, path)


def draw_cache(data, path):
    fig, ax = _axes()
    values, labels = data["values"], data["labels"]
    bars = ax.bar(labels, values, color=[MUTED, ACC, "#F87171"], width=.42)
    ax.bar_label(bars, labels=[f"${v:,.3f}" for v in values], padding=6, color=FG, fontsize=16, fontweight="bold")
    ax.set_ylim(0, max(values) * 1.22)
    _clean(ax, "y", "같은 100콜, 캐시 조건만 바꿈 (Sonnet 4.6 단가)")
    _close(fig, path)


def draw_turns(data, path):
    fig, ax = _axes()
    turns = list(data["turns"])
    costs = [data["turns"][t]["cost_usd"] for t in turns]
    bars = ax.bar(turns, costs, color=ACC, width=.5)
    ax.bar_label(bars, labels=[f"${c:,.2f}" for c in costs], padding=6, color=ACC, fontsize=14, fontweight="bold")
    twenty = data["turns"]["20"]["cost_usd"]
    lines = [f"20턴 세션 · 캐싱만 ${twenty:,.2f}"]
    for every, cost in sorted(data["compaction_20_turns"].items(), reverse=True):
        lines.append(f"{every}턴마다 컴팩션 ${cost:,.2f} (-{100 - cost / twenty * 100:.0f}%)")
    ax.text(0.02, 0.97, "\n".join(lines), transform=ax.transAxes, va="top", ha="left",
            color=ACC2, fontsize=12.5, linespacing=1.5)
    ax.set_ylim(0, max(costs) * 1.20)
    ax.set_xlabel("턴 수", fontsize=13)
    _clean(ax, "y", f"턴 수에 따른 세션 비용 ({data['model']}, 고정 {data['base_tokens']:,}토큰 프리픽스)")
    _close(fig, path)


def draw_stack(data, path):
    fig, ax = _axes()
    layers = data["layers"]
    x = list(range(1, len(layers) + 1))
    remaining = [100.0] + [l["remaining_after_pct"] for l in layers]
    ax.plot([0] + x, remaining, color=ACC, linewidth=2.6, marker="o", markersize=8)
    for i, layer in enumerate(layers, 1):
        ax.annotate(f"{layer['lever']}\n-{layer['cut_pct']:.0f}%", (i, remaining[i]),
                    textcoords="offset points", xytext=(0, 16), ha="center", color=MUTED, fontsize=12)
    ax.annotate(f"잔여 {data['remaining_pct']:.2f}%", (len(layers), remaining[-1]), textcoords="offset points",
                xytext=(-6, -34), ha="right", color=FG, fontsize=16, fontweight="bold")
    ax.set_xticks([0] + x, ["기준"] + [""] * len(layers))
    ax.set_ylim(0, 116)
    ax.set_xlim(-0.4, len(layers) + 0.4)
    _clean(ax, "y", "레버를 순서대로 적용한 잔여 비용 (%)")
    _close(fig, path)


def draw_thinking(data, path):
    import matplotlib.ticker as mticker
    fig, ax = _axes(left=0.13)
    labels = list(data["by_budget"])
    values = [data["by_budget"][l] for l in labels]
    bars = ax.bar(labels, values, color=[MUTED, MUTED, ACC2, ACC2, ACC], width=.5)
    ax.set_yscale("log")
    ax.set_ylim(min(values) * .5, max(values) * 8)
    ticks = [1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3]
    ax.set_yticks(ticks, [f"${t:,.5f}".rstrip("0") for t in ticks])
    ax.yaxis.set_minor_locator(mticker.NullLocator())
    for bar, value in zip(bars, values):
        ax.annotate(f"${value:,.6f}", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    textcoords="offset points", xytext=(0, 6), ha="center", color=FG, fontsize=12, fontweight="bold")
    _clean(ax, "y", "사고 예산별 호출당 비용 (저장 로그 재계산, 로그 축)")
    _close(fig, path)


def draw_case_tokens(data, path):
    fig, ax = _axes()
    modes = ["vibe", "spec"]
    names = ["Vibe (한 문장 지시)", "Spec (4필드 스펙)"]
    parts = ["uncached_input", "reasoning_plus_output", "cached"]
    part_labels = ["비캐시 입력", "추론+보이는 출력", "캐시 입력(추정)"]
    colors = [ACC2, ACC, MUTED]
    bottoms = [0, 0]
    for part, label, color in zip(parts, part_labels, colors):
        values = [data["modes"][m][part] for m in modes]
        ax.bar(names, values, bottom=bottoms, color=color, width=.44, label=label)
        for i, (value, bottom) in enumerate(zip(values, bottoms)):
            if value > 700:
                ax.annotate(f"{value:,}", (i, bottom + value / 2), ha="center", va="center",
                            color=BG, fontsize=13, fontweight="bold")
        bottoms = [b + v for b, v in zip(bottoms, values)]
    for i, mode in enumerate(modes):
        total = sum(data["modes"][mode][p] for p in parts)
        ax.annotate(f"합계 {total:,}", (i, bottoms[i]), textcoords="offset points", xytext=(0, 10),
                    ha="center", color=FG, fontsize=14, fontweight="bold")
    ax.set_ylim(0, max(bottoms) * 1.22)
    _clean(ax, "y", "두 산출물의 토큰 구조 (추정 usage)")
    handles = [plt_patch(color=c, label=l) for c, l in zip(colors, part_labels)]
    fig.legend(handles=handles, facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=12,
               ncol=3, framealpha=1, loc="upper right", bbox_to_anchor=(0.99, 0.995))
    _close(fig, path)


def draw_case_bases(data, path):
    fig, ax = _axes()
    keys = list(data["bases"])
    names = [data["bases"][k]["name"].replace(" (", "\n(") for k in keys]
    vibe = [data["bases"][k]["vibe_usd"] for k in keys]
    spec = [data["bases"][k]["spec_usd"] for k in keys]
    x = list(range(len(keys)))
    ax.bar([i - 0.19 for i in x], vibe, width=.36, color=MUTED, label="Vibe")
    ax.bar([i + 0.19 for i in x], spec, width=.36, color=ACC, label="Spec")
    top = max(vibe + spec)
    for i, key in enumerate(keys):
        ax.annotate(f"{data['bases'][key]['delta_pct']:.1f}%", (i, top * 1.16), ha="center", va="bottom",
                    color=FG, fontsize=14, fontweight="bold")
        ax.annotate(f"${vibe[i]:.4f}", (i - 0.19, vibe[i]), textcoords="offset points", xytext=(0, 4),
                    ha="center", color=MUTED, fontsize=11)
        ax.annotate(f"${spec[i]:.4f}", (i + 0.19, spec[i]), textcoords="offset points", xytext=(0, 4),
                    ha="center", color=ACC, fontsize=11)
    ax.set_xticks(x, names, fontsize=12)
    handles = [plt_patch(color=MUTED, label="Vibe"), plt_patch(color=ACC, label="Spec")]
    fig.legend(handles=handles, facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=12,
               ncol=2, framealpha=1, loc="upper right", bbox_to_anchor=(0.99, 0.995))
    ax.set_ylim(0, top * 1.42)
    _clean(ax, "y", "같은 추정 usage를 세 단가로 환산 (USD)")
    _close(fig, path)



def draw_monthly(data, path):
    fig, ax = _axes(left=0.09)
    names = list(data["by_model"])
    a = [data["by_model"][n]["A"] for n in names]
    b = [data["by_model"][n]["B"] for n in names]
    x = list(range(len(names)))
    ax.bar([i - 0.19 for i in x], a, width=.36, color=MUTED, label="A · 대충 지시 (입력 2,000 / 출력 12,000)")
    ax.bar([i + 0.19 for i in x], b, width=.36, color=ACC, label="B · 스펙 주입 (입력 6,000 / 출력 3,000)")
    for i in x:
        ax.annotate(f"${a[i]:,.0f}", (i - 0.19, a[i]), textcoords="offset points", xytext=(0, 5),
                    ha="center", color=MUTED, fontsize=12)
        ax.annotate(f"${b[i]:,.0f}", (i + 0.19, b[i]), textcoords="offset points", xytext=(0, 5),
                    ha="center", color=ACC, fontsize=12, fontweight="bold")
        ax.annotate(f"-{(1 - b[i] / a[i]) * 100:.0f}%", (i, max(a[i], b[i])), textcoords="offset points",
                    xytext=(0, 24), ha="center", color=FG, fontsize=13, fontweight="bold")
    ax.set_xticks(x, names, fontsize=13)
    ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=11.5, loc="upper right", framealpha=1)
    ax.set_ylim(0, max(a) * 1.34)
    _clean(ax, "y", f"모델별 월 청구서 — 같은 {data['jobs_per_month']:,}건, 두 워크플로 (USD)")
    _close(fig, path)


def draw_cache_hit(data, path):
    fig, ax = _axes(left=0.09)
    rates = [float(k) for k in data["by_hit_rate"]]
    costs = [data["by_hit_rate"][k] for k in data["by_hit_rate"]]
    ax.plot(rates, costs, color=ACC, linewidth=3, marker="o", markersize=9)
    ax.hlines(data["no_cache_usd"], -0.02, 1.02, colors=MUTED, linestyles="solid", linewidth=1.6)
    ax.annotate(f"캐시 없음 ${data['no_cache_usd']:,.3f}", (1.0, data["no_cache_usd"]), color=MUTED,
                fontsize=13, ha="right", va="bottom", textcoords="offset points", xytext=(0, 6))
    be = data["breakeven_hit_rate"]
    ax.axvline(be, color="#F87171", linestyle="dashed", linewidth=1.6)
    ax.annotate(f"손익분기 {be * 100:.1f}%", (be, max(costs)), color="#F87171", fontsize=13.5,
                ha="center", va="bottom", textcoords="offset points", xytext=(0, 8), fontweight="bold")
    for rate, cost in zip(rates, costs):
        ax.annotate(f"${cost:,.3f}", (rate, cost), textcoords="offset points", xytext=(0, 14),
                    ha="center", color=FG, fontsize=12)
    ax.set_xticks(rates, [f"{r * 100:.0f}%" for r in rates], fontsize=13)
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(min(costs) * 0.72, max(costs) * 1.30)
    _clean(ax, "y", "프롬프트 캐시 적중률에 따른 100콜 비용 (Sonnet 4.6)")
    _close(fig, path)


def draw_usage_mix(data, path):
    fig, ax = _axes(left=0.16)
    parts = list(data["parts"])
    shares = [data["shares_pct"][p] for p in parts]
    colors = [ACC2, "#F0A868", ACC]
    left = 0.0
    for part, share, color in zip(parts, shares, colors):
        ax.barh([0], [share], left=left, color=color, height=.42, label=f"{part}  {share:.1f}%")
        if share >= 12:
            ax.annotate(f"{data['parts'][part]:,}토큰", (left + share / 2, 0), ha="center", va="center",
                        color=BG, fontsize=13, fontweight="bold")
        elif share >= 6:
            ax.annotate(f"{data['parts'][part]:,}토큰", (left + share / 2, 0.235), ha="center", va="bottom",
                        color=color, fontsize=12, fontweight="bold")
        else:
            ax.annotate(f"{data['parts'][part]:,}토큰", (left - 0.8, 0.235), ha="right", va="bottom",
                        color=color, fontsize=12, fontweight="bold")
        left += share
    ax.set_yticks([])
    ax.set_xlim(0, 100)
    ax.set_xticks(list(range(0, 101, 25)), [f"{v}%" for v in range(0, 101, 25)], fontsize=13)
    ax.set_ylim(-0.42, 0.42)
    ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=12.5, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), ncol=3, framealpha=1)
    ax.set_ylim(-0.5, 0.5)
    _clean(ax, "x", f"{data['turns']}턴 세션에서 무엇이 토큰을 쓰는가 (총 {data['total']:,}토큰)")
    ax.set_title(ax.get_title(), pad=52)
    _close(fig, path)


DRAWERS = {"prices": draw_prices, "tokenizer": draw_tokenizer, "cache": draw_cache,
           "turns": draw_turns, "stack": draw_stack, "thinking": draw_thinking,
           "case_tokens": draw_case_tokens, "case_bases": draw_case_bases,
           "monthly": draw_monthly, "cache_hit": draw_cache_hit, "usage_mix": draw_usage_mix}
FILES = {"prices": "prices.png", "tokenizer": "tokenizer.png", "cache": "cache.png",
         "turns": "turns.png", "stack": "stack.png", "thinking": "thinking.png",
         "case_tokens": "case_tokens.png", "case_bases": "case_bases.png",
         "monthly": "monthly.png", "cache_hit": "cache_hit.png", "usage_mix": "usage_mix.png"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_all(out_dir=None, data=None):
    out = Path(out_dir or ROOT / "presentation/charts")
    out.mkdir(parents=True, exist_ok=True)
    data = data or _load()
    import matplotlib
    for name, drawer in DRAWERS.items():
        drawer(data[name], out / FILES[name])
    manifest = {
        "generated_by": "presentation/deckgen/make_charts.py",
        "figure": {"figsize": list(FIGSIZE), "dpi": DPI, "font": FONT, "matplotlib": matplotlib.__version__,
                   "background": BG, "accent": ACC},
        "note": "계열값은 pricing·evidence·저장 자료에서 계산한다. 슬라이드에는 이 파일만 삽입하며, 테스트가 "
                "manifest의 계열값과 파일 해시를 다시 대조한다.",
        "charts": {name: {"file": FILES[name], "sha256": sha256(out / FILES[name]), **data[name]}
                   for name in DRAWERS},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(DRAWERS)} charts + manifest.json to {out}")
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path)
    args = ap.parse_args()
    build_all(args.out_dir)


if __name__ == "__main__":
    main()
