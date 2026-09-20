#!/usr/bin/env python3
"""exp11: tool-context cost scenarios + optional 3-request Gemini probe.

A: every task turn reads K tool tokens. Main, child and compaction calls are all
priced. This is an equal-tool-work scenario, not a quality-matched experiment.
B: request 1 asks for a local tool; request 2 first injects its response;
request 3 replays that same tool response in history. Only B uses a paid API.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import pricing, report

SYNTH_FILE = "\n".join(f"def handler_{i:03d}(payload):  # service={i % 7} -> validate rule {i}, persist and return" for i in range(400))
TOOL = {"functionDeclarations": [{"name": "read_file", "description": "Read a text file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}]}
SYSTEM = "Use read_file for the requested file, then answer with one sentence."


def simulate(turns, tool_tok, base, agent_out, strategy, every=10, summary=1500):
    """Counts, not empirical outcomes. One K-token tool result per task turn."""
    if strategy not in {"naive", "compact", "subagent"}:
        raise ValueError(strategy)
    if turns < 1 or every < 1 or min(tool_tok, base, agent_out, summary) < 0:
        raise ValueError("invalid scenario parameters")
    counts = dict(main_in=0, main_out=turns * agent_out, child_in=0, child_out=0,
                  compact_in=0, compact_out=0)
    history = base
    for t in range(turns):
        if strategy == "subagent":
            # Each child sees the same amount of tool material as naive.
            counts["child_in"] += base + tool_tok
            counts["child_out"] += summary
            history += summary
        else:
            history += tool_tok
        counts["main_in"] += history
        history += agent_out
        if strategy == "compact" and (t + 1) % every == 0 and t < turns - 1:
            counts["compact_in"] += history
            counts["compact_out"] += summary
            history = base + summary
    return counts


def sim_loop(turns, tool_tok, base, agent_out, strategy, every=10, summary=1500):
    """Compatibility: main input only; do not label this whole-system cost."""
    return simulate(turns, tool_tok, base, agent_out, strategy, every, summary)["main_in"]


def scenario_cost(m, counts):
    return pricing.cost(m, counts["main_in"] + counts["child_in"] + counts["compact_in"],
                        counts["main_out"] + counts["child_out"] + counts["compact_out"])


def mode_sim(args, m):
    print("A. 시나리오: 매 턴 K 토큰 툴 읽기, 동일 모델 단가, 캐싱·품질 차이 미포함")
    print(f"turns={args.turns}, K={args.tool_tokens}, base={args.base}, output={args.agent_out}, summary={args.summary}")
    import tiktoken
    print("합성 파일의 로컬 인코딩(모형 K와 별개):", len(tiktoken.get_encoding("o200k_base").encode(SYNTH_FILE)))
    for strategy in ("naive", "compact", "subagent"):
        counts = simulate(args.turns, args.tool_tokens, args.base, args.agent_out, strategy,
                          args.every, args.summary)
        print(strategy, json.dumps({**counts, "whole_system_usd": scenario_cost(m, counts)}))
    repeated = args.tool_tokens * args.turns * (args.turns + 1) // 2
    print(f"naive 툴 성분의 누적 전송 = K*N*(N+1)/2 = {repeated:,} 토큰")
    print("기존 −87%는 자식·요약 비용이 빠진 메인 컨텍스트 모형이었다. 전체 절감 실측으로 쓰지 않는다.")


def _post(url, payload, key):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
    with urllib.request.urlopen(req, timeout=240) as response:
        return json.loads(response.read())


def content_from(response):
    candidates = response.get("candidates") or []
    if not candidates or not candidates[0].get("content"):
        raise ValueError("response has no candidate content")
    # Preserve ALL parts, thoughtSignature and functionCall id verbatim.
    return copy.deepcopy(candidates[0]["content"])


def follow_up(contents, response, tool_text):
    model_content = content_from(response)
    calls = [p["functionCall"] for p in model_content.get("parts", []) if "functionCall" in p]
    if len(calls) != 1 or calls[0].get("name") != "read_file":
        raise ValueError("expected exactly one read_file functionCall")
    fc = calls[0]
    fr = {"name": fc["name"], "response": {"content": tool_text}}
    if "id" in fc:
        fr["id"] = fc["id"]
    return contents + [model_content, {"role": "user", "parts": [{"functionResponse": fr}]}]


def mode_live(args, m, key):
    print(f"B. LIVE — {args.api_model}, price={m.name}; new requests are billable")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{args.api_model}:generateContent"
    contents = [{"role": "user", "parts": [{"text": "Read docs/service.py and name its first three functions."}]}]
    records, run_id = [], str(uuid.uuid4())
    for i in range(3):
        payload = {"contents": contents, "systemInstruction": {"parts": [{"text": SYSTEM}]},
                   "tools": [TOOL], "generationConfig": {"maxOutputTokens": 4000},
                   "toolConfig": {"functionCallingConfig": {"mode": "ANY" if i == 0 else "NONE"}}}
        rec = {"run_id": run_id, "step": i + 1, "model": args.api_model, "payload": payload,
               "price_model": m.name, "price_input": m.inp, "price_output": m.out,
               "price_checked": m.verified_on,
               "price_override": bool(getattr(args, "price_model", None))}
        failure = None
        try:
            response = _post(url, payload, key)
            rec["response"] = response
            usage = response.get("usageMetadata") or {}
            if not all(k in usage for k in ("promptTokenCount", "candidatesTokenCount")):
                raise ValueError("missing usage; do not report a zero-cost success")
            rec["cost_usd"] = pricing.gemini_usage_cost(m, usage)
            cand = (response.get("candidates") or [{}])[0]
            if cand.get("finishReason") != "STOP":
                raise ValueError("truncated/unfinished response; live probe incomplete")
            if i == 0:
                contents = follow_up(contents, response, SYNTH_FILE)
            else:
                contents = contents + [content_from(response), {"role": "user", "parts": [{"text": "Using the file already read, repeat the first function name only."}]}]
            rec["valid"] = True
        except Exception as exc:
            failure = exc
            rec.update(valid=False, error=type(exc).__name__ + ": request/probe failed")
        records.append(rec)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"step={i+1}: valid={rec['valid']}; observed usage cost={rec.get('cost_usd', 'unknown')}")
        if failure is not None:
            raise RuntimeError(f"step {i+1} incomplete; recorded as failure, not confirmed") from failure
    print("step2는 툴 내용의 첫 모델 입력, step3가 이력 재전송이다 (step1에는 파일 내용 없음).")
    print("toolUsePromptTokenCount는 별도 관측 필드다. 로컬 함수 응답 크기나 추가 청구액으로 자동 간주하지 않는다.")
    print("3개 요청의 관측이며, 요약/서브에이전트의 품질 동등 절감 효과를 검증하지 않았다.")
    return records


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="sonnet", help="simulation price key")
    ap.add_argument("--turns", type=int, default=20)
    ap.add_argument("--tool-tokens", type=int, default=8000)
    ap.add_argument("--base", type=int, default=5000)
    ap.add_argument("--agent-out", type=int, default=300)
    ap.add_argument("--summary", type=int, default=1500)
    ap.add_argument("--every", type=int, default=10)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--api-model", default="gemini-3.1-flash-lite")
    ap.add_argument("--price-model", help="explicit live price override; otherwise map API model")
    ap.add_argument("--out", type=Path, default=Path("results/tool_bloat_new.jsonl"))
    args = ap.parse_args()
    mode_sim(args, pricing.get(args.model))
    if args.live:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise SystemExit("SKIP live: GEMINI_API_KEY missing — not verified")
        m = pricing.get(args.price_model) if args.price_model else pricing.for_api(args.api_model)
        mode_live(args, m, key)


if __name__ == "__main__":
    main()
