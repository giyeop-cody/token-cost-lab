# -*- coding: utf-8 -*-
"""
한국어 vs 영어 실호출 벤치마크 (표본 확대판)

exp08 은 시연용 1회 호출이다. 이 스크립트는 통계를 내기 위해
같은 과제를 N회 반복하고 결과를 JSONL 로 한 줄씩 즉시 기록한다.

  - 모델 고정 (폴백으로 모델이 섞이면 비교가 무의미해짐)
  - maxOutputTokens 를 넉넉히 (잘리면 한국어가 과소평가됨)
  - finishReason 을 기록해서 잘린 표본을 사후에 제외
  - 429/500/503 은 지수 백오프 재시도
  - 한 호출 끝날 때마다 flush → 중간에 죽어도 데이터가 남는다

  python tools/live_lang_bench.py --n 25 --model gemini-3.1-flash-lite
  python tools/live_lang_bench.py --summarize results/live_lang_thinking.jsonl
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models"
RETRY = {429, 500, 502, 503, 504}

TASKS = {
    # 설명형 — 출력이 실제로 길게 나오는 과제
    "explain": {
        "en": "Explain what prompt caching is and when it saves money. "
              "Answer in English in about 120 words.",
        "ko": "프롬프트 캐싱이 무엇이고 언제 비용을 절감하는지 설명하세요. "
              "한국어로 약 120단어 분량으로 답하세요.",
    },
    # 추론형 — 사고 토큰이 많이 나오는 과제
    "reason": {
        "en": "A team makes 1,760 API calls a month. Each call sends a 12,000 token "
              "system prompt. Caching cuts repeated input to 10% of the rate. "
              "Input is $2 per million tokens. Compute the monthly saving. "
              "Show your reasoning briefly in English.",
        "ko": "한 팀이 월 1,760회 API를 호출합니다. 매 호출마다 12,000 토큰의 "
              "시스템 프롬프트를 보냅니다. 캐싱하면 반복 입력이 단가의 10%가 됩니다. "
              "입력 단가는 100만 토큰당 2달러입니다. 월 절감액을 계산하세요. "
              "한국어로 근거를 간단히 보이세요.",
    },
}


def key() -> str:
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not k:
        raise SystemExit("GEMINI_API_KEY 없음")
    return k


def call(model, text, k, maxout=4000, timeout=240, budget=None):
    """budget: None=미지정(모델 기본) · 0=사고 끔 · -1=자동 · N=예산 N토큰"""
    url = f"{API}/{model}:generateContent"
    gc = {"maxOutputTokens": maxout}
    if budget is not None:
        gc["thinkingConfig"] = {"thinkingBudget": budget}
    payload = {"contents": [{"parts": [{"text": text}]}],
               "generationConfig": gc}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": k},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    u = d.get("usageMetadata", {}) or {}
    cand = (d.get("candidates") or [{}])[0]
    txt = "".join(p.get("text", "")
                  for p in (cand.get("content", {}) or {}).get("parts", []) or [])
    return {
        "prompt": int(u.get("promptTokenCount", 0) or 0),
        "thoughts": int(u.get("thoughtsTokenCount", 0) or 0),
        "cands": int(u.get("candidatesTokenCount", 0) or 0),
        "cached": int(u.get("cachedContentTokenCount", 0) or 0),
        "total": int(u.get("totalTokenCount", 0) or 0),
        "finish": cand.get("finishReason", ""),
        "chars": len(txt),
    }


def robust(model, text, k, maxout, budget=None):
    delay = 5.0
    for attempt in range(8):
        try:
            return call(model, text, k, maxout, budget=budget)
        except urllib.error.HTTPError as e:
            if e.code in RETRY:
                time.sleep(delay)
                delay = min(delay * 1.8, 90)
                continue
            return {"error": f"HTTP {e.code}", "body": e.read().decode()[:200]}
        except Exception as e:  # 타임아웃·네트워크
            time.sleep(delay)
            delay = min(delay * 1.8, 90)
    return {"error": "retries exhausted"}


def run(args):
    k = key()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    f = open(args.out, "a", encoding="utf-8")
    total = args.n * len(args.tasks) * 2
    done = 0
    for i in range(args.n):
        for task in args.tasks:
            for lang in ("en", "ko"):
                rec = robust(args.model, TASKS[task][lang], k, args.maxout,
                                     budget=args.thinking)
                rec.update({"i": i, "task": task, "lang": lang,
                            "model": args.model, "budget": args.thinking,
                            "ts": time.time()})
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                done += 1
                tag = rec.get("error", f"{rec.get('thoughts')}th/{rec.get('cands')}c")
                print(f"  [{done}/{total}] {task}/{lang}  {tag}", flush=True)
                time.sleep(args.sleep)
    f.close()
    print("완료:", args.out, flush=True)
    summarize(args.out)


def summarize(path):
    import statistics as st
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    ok = [r for r in rows if "error" not in r]
    print(f"\n{'='*76}\n  표본 {len(rows)}건 중 성공 {len(ok)}건")
    trunc = [r for r in ok if r.get("finish") not in ("STOP", "")]
    if trunc:
        print(f"  ⚠️ 잘린 표본 {len(trunc)}건 (finishReason != STOP) — 평균에서 제외")
    ok = [r for r in ok if r.get("finish") == "STOP"]

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from lab.pricing import log_cost
    print("  모델별 Standard 단가 환산 (2026-09-20), 실제 청구서 아님")
    for task in sorted({r["task"] for r in ok}):
        print(f"\n── 과제: {task} " + "─" * 50)
        agg = {}
        for lang in ("en", "ko"):
            d = [r for r in ok if r["task"] == task and r["lang"] == lang]
            if not d:
                continue
            agg[lang] = {
                "n": len(d),
                "prompt": st.mean(r["prompt"] for r in d),
                "thoughts": st.mean(r["thoughts"] for r in d),
                "cands": st.mean(r["cands"] for r in d),
                "th_sd": st.stdev([r["thoughts"] for r in d]) if len(d) > 1 else 0,
                "ca_sd": st.stdev([r["cands"] for r in d]) if len(d) > 1 else 0,
            }
        if len(agg) < 2:
            continue
        print(f"  {'언어':<6}{'n':>4}{'입력':>8}{'사고':>9}{'응답':>9}{'출력계':>9}{'비용':>12}")
        cost = {}
        for lang in ("en", "ko"):
            a = agg[lang]
            out = a["thoughts"] + a["cands"]
            c = st.mean(log_cost(r) for r in ok if r["task"] == task and r["lang"] == lang)
            cost[lang] = c
            print(f"  {lang.upper():<6}{a['n']:>4}{a['prompt']:>8.0f}"
                  f"{a['thoughts']:>9.0f}{a['cands']:>9.0f}{out:>9.0f}{c:>12.6f}")
        print(f"  {'':6}{'':4}{'':8}{'±'+format(agg['ko']['th_sd'],'.0f'):>9}"
              f"{'±'+format(agg['ko']['ca_sd'],'.0f'):>9}   (KO 표준편차)")
        if cost["en"]:
            print(f"\n  한국어 추가 비용   {(cost['ko']/cost['en']-1)*100:+.1f}%")
            print(f"  입력 배수 {agg['ko']['prompt']/max(agg['en']['prompt'],1):.2f}×  ·  "
                  f"사고 배수 {agg['ko']['thoughts']/max(agg['en']['thoughts'],1):.2f}×  ·  "
                  f"응답 배수 {agg['ko']['cands']/max(agg['en']['cands'],1):.2f}×")
    print(f"\n{'='*76}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--model", default="gemini-3.1-flash-lite")
    ap.add_argument("--tasks", nargs="+", default=["explain", "reason"])
    ap.add_argument("--maxout", type=int, default=4000)
    ap.add_argument("--thinking", type=int, default=None,
                    help="사고 예산: 0=끔, -1=자동, N=N토큰. 미지정이면 모델 기본값")
    ap.add_argument("--sleep", type=float, default=1.5)
    ap.add_argument("--out", default="results/live_lang_new.jsonl")
    ap.add_argument("--allow-legacy-budget", action="store_true",
                    help="opt in to historical Gemini 3 thinkingBudget requests, not current documented thinkingLevel")
    ap.add_argument("--summarize", help="기존 JSONL 요약만")
    args = ap.parse_args()
    if args.summarize:
        summarize(args.summarize)
    else:
        if args.n < 1:
            ap.error("--n must be positive")
        if args.thinking is not None and args.model.startswith("gemini-3") and not args.allow_legacy_budget:
            ap.error("Current Gemini 3 thinking control is thinkingLevel. Use exp10, or explicitly --allow-legacy-budget for historical request replay; not pre-verified.")
        run(args)


if __name__ == "__main__":
    main()
