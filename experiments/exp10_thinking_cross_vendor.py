#!/usr/bin/env python3
"""exp10: paid cross-vendor usage probe, NOT a pre-confirmed result.

Offline: --dry-run. Live: --vendor all --n 5 --out results/cross_vendor_new.jsonl.
A single arithmetic question is repeated. Repetition is not task diversity or
quality equivalence. Parameters must be supported by the selected model.
Billing semantics come from vendor docs; usage fields alone do not verify an invoice.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import pricing

QUESTION = ("A cache holds 20,000 tokens. Cached reads cost 25% of the input rate. "
            "If the input rate is $2 per million tokens, how much do 100 cached "
            "reads cost? Answer with the number only.")
# Fixed maximum output per vendor: do not confound thinking setting with output cap.
LEVELS = {
    "gemini": [("minimal", "minimal", 12000), ("low", "low", 12000), ("high", "high", 12000)],
    "anthropic": [("off", None, 12000), ("low (1024)", 1024, 12000), ("high (8192)", 8192, 12000)],
    "openai": [("minimal", "minimal", 12000), ("low", "low", 12000), ("high", "high", 12000)],
}
DEFAULTS = {"gemini": ("flash-lite", "gemini-3.1-flash-lite"),
            "anthropic": ("haiku", "claude-haiku-4-5"), "openai": ("gpt5", "gpt-5")}


def _post(url, payload, headers):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=240) as response:
        return json.loads(response.read())


def call_gemini(model, level, budget, max_out, key):
    config = {"thinkingBudget": budget} if isinstance(budget, int) else {"thinkingLevel": budget}
    data = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                 {"contents": [{"role": "user", "parts": [{"text": QUESTION}]}],
                  "generationConfig": {"maxOutputTokens": max_out, "thinkingConfig": config}},
                 {"x-goog-api-key": key})
    u = data.get("usageMetadata") or {}
    c = (data.get("candidates") or [{}])[0]
    parts = (c.get("content") or {}).get("parts") or []
    return {"level": level, "inp": int(u.get("promptTokenCount", 0)),
            "out": int(u.get("candidatesTokenCount", 0)) + int(u.get("thoughtsTokenCount", 0)),
            "think": int(u.get("thoughtsTokenCount", 0)), "vis": int(u.get("candidatesTokenCount", 0)),
            "cached": int(u.get("cachedContentTokenCount", 0)), "cache_write": 0,
            "text": "".join(p.get("text", "") for p in parts if not p.get("thought")).strip(),
            "finish": c.get("finishReason"), "complete": c.get("finishReason") == "STOP",
            "usage_present": "promptTokenCount" in u and "candidatesTokenCount" in u,
            "usage": u, "method": "usageMetadata", "resolved_model": data.get("modelVersion", model)}


def call_anthropic(model, level, budget, max_out, key):
    payload = {"model": model, "max_tokens": max_out,
               "messages": [{"role": "user", "content": QUESTION}]}
    if budget is not None:
        payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
    else:
        payload["thinking"] = {"type": "disabled"}
    d = _post("https://api.anthropic.com/v1/messages", payload,
              {"x-api-key": key, "anthropic-version": "2023-06-01"})
    u = d.get("usage") or {}
    think = (u.get("output_tokens_details") or {}).get("thinking_tokens")
    think = int(think) if think is not None else None
    # Claude's fresh input EXCLUDES cache read/write. Preserve all three buckets.
    return {"level": level, "inp": int(u.get("input_tokens", 0)) + int(u.get("cache_read_input_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0)),
            "out": int(u.get("output_tokens", 0)), "think": think,
            "vis": int(u.get("output_tokens", 0)) - think if think is not None else None,
            "cached": int(u.get("cache_read_input_tokens", 0)), "cache_write": int(u.get("cache_creation_input_tokens", 0)),
            "text": "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text").strip(),
            "finish": d.get("stop_reason"), "complete": d.get("stop_reason") == "end_turn",
            "usage_present": "input_tokens" in u and "output_tokens" in u,
            "usage": u, "method": "output_tokens_details.thinking_tokens if present; otherwise split unobserved (never tiktoken subtraction)",
            "resolved_model": d.get("model", model)}


def call_openai(model, level, effort, max_out, key):
    d = _post("https://api.openai.com/v1/chat/completions",
              {"model": model, "max_completion_tokens": max_out, "reasoning_effort": effort,
               "messages": [{"role": "user", "content": QUESTION}]}, {"Authorization": f"Bearer {key}"})
    u = d.get("usage") or {}
    c = (d.get("choices") or [{}])[0]
    think = int((u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0))
    out = int(u.get("completion_tokens", 0))
    return {"level": level, "inp": int(u.get("prompt_tokens", 0)), "out": out,
            "think": think, "vis": out - think,
            "cached": int((u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)), "cache_write": 0,
            "text": ((c.get("message") or {}).get("content") or "").strip(),
            "finish": c.get("finish_reason"), "complete": c.get("finish_reason") == "stop",
            "usage_present": "prompt_tokens" in u and "completion_tokens" in u,
            "usage": u, "method": "completion_tokens_details", "resolved_model": d.get("model", model)}


def observed_cost(r, m):
    if r["think"] is not None and not 0 <= r["think"] <= r["out"]:
        raise ValueError("thinking must be a subset of output")
    if r["cache_write"] < 0 or r["cache_write"] + r["cached"] > r["inp"]:
        raise ValueError("invalid input cache buckets")
    # cost() subtracts cache reads once; add only the write premium (5m TTL).
    return (pricing.cost(m, r["inp"], r["out"], r["cached"])
            + r["cache_write"] * m.inp * (m.cache_write - 1) / 1e6)


def run_vendor(vendor, args, key):
    price_key, default_model = DEFAULTS[vendor]
    model = getattr(args, f"model_{vendor}", None) or default_model
    override = getattr(args, f"price_model_{vendor}", None)
    m = pricing.get(override) if override else pricing.for_api(model)
    records = []
    # Rotate order over repetitions to reduce fixed order confounding; still no random task sample.
    levels = LEVELS[vendor]
    for i in range(args.n):
        for label, param, max_out in levels[i % len(levels):] + levels[:i % len(levels)]:
            rec = {"run_id": args.run_id, "vendor": vendor, "model": model, "level": label,
                   "parameter": param, "max_output": max_out, "i": i, "ts": time.time(),
                   "question": QUESTION, "price_model": m.name,
                   "price_basis": ("explicit counterfactual override: " if override else "") + m.basis,
                   "price_override": bool(override),
                   "price_input": m.inp, "price_output": m.out, "price_checked": m.verified_on}
            try:
                r = {"gemini": call_gemini, "anthropic": call_anthropic, "openai": call_openai}[vendor](model, label, param, max_out, key)
                rec.update(r)
                if not r["usage_present"]:
                    raise ValueError("missing usage is not zero observed cost")
                rec["cost_usd"] = observed_cost(r, m)
                try:
                    rec["correct"] = abs(float(r["text"].removeprefix("$")) - 1.0) <= 1e-9
                except ValueError:
                    rec["correct"] = False
                rec["valid"] = bool(r["complete"] and r["usage_present"] and r["text"])
            except (Exception, SystemExit) as e:
                # HTTP response bodies may contain echoed inputs; never log auth headers/keys.
                rec.update(valid=False, error=type(e).__name__ + ": request failed")
            records.append(rec)
            if getattr(args, "out", None):
                args.out.parent.mkdir(parents=True, exist_ok=True)
                with args.out.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(json.dumps(rec, ensure_ascii=False))
    valid = [r for r in records if r.get("valid")]
    print(f"{vendor}: valid {len(valid)}/{len(records)}; observed correct {sum(r['correct'] for r in valid)}/{len(valid)}")
    observed_cost_usd = sum(r.get("cost_usd", 0) for r in records)
    print(f"Observed usage cost (including incomplete responses): ${observed_cost_usd:.8f}; missing usage is not known to be free")
    return {"records": records, "valid": len(valid), "attempted": len(records),
            "observed_cost_usd": observed_cost_usd}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vendor", choices=["all", *DEFAULTS], default="all")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("results/cross_vendor_new.jsonl"))
    ap.add_argument("--dry-run", action="store_true")
    for vendor in DEFAULTS:
        ap.add_argument(f"--model_{vendor}")
        ap.add_argument(f"--price_model_{vendor}", help="Explicit counterfactual price override (not automatic)")
    args = ap.parse_args()
    if args.n < 1:
        ap.error("--n must be positive")
    args.run_id = str(uuid.uuid4())
    if args.dry_run:
        print("DRY RUN — no requests, no measured outcomes")
        print(json.dumps({"question": QUESTION, "models": DEFAULTS, "levels": LEVELS}, ensure_ascii=False, indent=2))
        print("Gemini: generationConfig.thinkingConfig.thinkingLevel; Claude: thinking; OpenAI: reasoning_effort")
        return 0
    keys = {"gemini": os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"),
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"), "openai": os.environ.get("OPENAI_API_KEY")}
    vendors = list(DEFAULTS) if args.vendor == "all" else [args.vendor]
    failed = False
    for vendor in vendors:
        if not keys[vendor]:
            print(f"SKIP {vendor}: key missing; not verified")
            failed = True
            continue
        result = run_vendor(vendor, args, keys[vendor])
        failed |= result["valid"] != result["attempted"]
    print("미검증/실패/절단 있음" if failed else "요청 및 usage 관측 완료 — 과금 규칙은 공식 문서 근거, 청구서 검증 아님")
    print("No cross-vendor accuracy/price multiplier conclusion is inferred from this one-question probe.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
