#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thinking_sweep.py — 과거 thinkingBudget 로그 재계산 또는 명시적 새 usage 관측.

기존 30행은 당시 요청 조건을 담은 저장 usage 기록이다. 현재 API 지원과 같다고 보장하지 않는다.
같은 질문 · 같은 모델 · 오직 thinkingBudget만 변경 → 사고 토큰이 요금에서
차지하는 비중을 분리 측정한다.

    python tools/thinking_sweep.py --n 5
    python tools/thinking_sweep.py --summarize results/thinking_sweep.jsonl

주의: 사고 토큰은 candidatesTokenCount에 포함되지 않으며 별도 필드
(thoughtsTokenCount)로 오지만, 과금은 출력 단가로 이루어진다.
"""
import argparse
import json
import os
import statistics as st
import time
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models"
RETRY = {429, 500, 502, 503, 504}

# 사고를 유도하되 최종 답은 짧은 질문 — "보이는 결과물은 같은데 요금만 다르다"를 보이기 위함
PROMPT = (
    "A team makes 1,760 API calls per month. Each call sends a 12,000 token "
    "system prompt. Prompt caching cuts repeated input to 10% of the base rate. "
    "The input rate is $2.00 per million tokens. "
    "Compute the exact monthly saving in USD. "
    "Reply with ONLY the final dollar amount, nothing else."
)

# (라벨, thinkingBudget)  None=미지정(모델 기본값)
LEVELS = [
    ("미지정(기본)", None),
    ("명시적 0", 0),
    ("512", 512),
    ("2048", 2048),
    ("자동 (-1)", -1),
]

# Prices are not usage metadata. Keep actual and historical conversion separate.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab.pricing import log_cost


def key() -> str:
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not k:
        raise SystemExit("GEMINI_API_KEY 없음")
    return k


def call(model, text, k, budget, maxout=4000, timeout=240):
    gc = {"maxOutputTokens": maxout}
    if budget is not None:
        gc["thinkingConfig"] = {"thinkingBudget": budget}
    req = urllib.request.Request(
        f"{API}/{model}:generateContent",
        data=json.dumps({"contents": [{"parts": [{"text": text}]}],
                         "generationConfig": gc}).encode(),
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
        "text": txt.strip()[:120],
    }


def robust(model, text, k, budget):
    delay = 5.0
    for _ in range(8):
        try:
            return call(model, text, k, budget)
        except urllib.error.HTTPError as e:
            if e.code in RETRY:
                time.sleep(delay)
                delay = min(delay * 1.8, 90)
                continue
            return {"error": f"HTTP {e.code}", "body": e.read().decode()[:200]}
        except Exception:
            time.sleep(delay)
            delay = min(delay * 1.8, 90)
    return {"error": "retries exhausted"}


def run(args):
    k = key()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    f = open(args.out, "a", encoding="utf-8")
    total = args.n * len(LEVELS)
    done = 0
    for i in range(args.n):
        for label, budget in LEVELS:
            rec = robust(args.model, PROMPT, k, budget)
            rec.update({"i": i, "label": label, "budget": budget,
                        "model": args.model, "ts": time.time()})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            done += 1
            tag = rec.get("error", f"{rec.get('thoughts')}th/{rec.get('cands')}c")
            print(f"  [{done}/{total}] {label:14} {tag}", flush=True)
            time.sleep(args.sleep)
    f.close()
    print("완료:", args.out, flush=True)
    summarize(args.out)


ANSWER, ANSWER_TOL = 38.016, 0.05


def wilson(k, n, z=1.96):
    """정답률의 Wilson 95% 신뢰구간. n=6은 매우 넓게 나온다 —
    '정답률이 떨어졌다'를 단정하지 말라는 근거를 숫자로 보여주기 위함."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - m) / d, (c + m) / d)


def numeric_answer(text):
    """Only accept a final numeric amount, not an arbitrary first number in prose."""
    import re
    m = re.fullmatch(r"\s*\$?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))(?:\s*USD)?\s*", text.replace(",", ""))
    return float(m[1]) if m else None


def n_correct(rows, tol=ANSWER_TOL):
    return sum((v := numeric_answer(r.get("text", ""))) is not None
               and abs(v - ANSWER) <= tol for r in rows)


def summarize(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    ok = [r for r in rows if "error" not in r and r.get("finish") == "STOP"]
    models = {r["model"] for r in ok}
    if len(models) != 1:
        raise ValueError(f"Compare one model per sweep; found {models}")
    print(f"\n{'='*100}\n사고 예산 스윕 — {len(rows)}건, STOP {len(ok)}건, 제외 {len(rows)-len(ok)}건")
    print(f"모델: {next(iter(models))}; 과제 1개 반복. 완료/허용오차 통과/정확한 정답을 구분한다.")
    print("actual=2026-09-20 Standard 단가 환산; legacy=발표 $1.25/$10 가정. 청구서 확인 아님.")
    groups = {budget: [r for r in ok if r.get("budget") == budget] for _, budget in LEVELS}
    base = groups[None]
    if not base:
        raise ValueError("미지정 기준 조건이 없습니다; 임의의 첫 행을 기준으로 쓰지 않습니다")
    means = {}
    for budget, g in groups.items():
        if g:
            means[budget] = {k: st.mean(log_cost(r, k) for r in g) for k in ("actual", "legacy")}
    print("예산 | n | 사고 평균 | 응답 평균 | actual $/호출 | actual/미지정 | legacy/미지정 | ±0.05 통과 [Wilson95%] | exact")
    for label, budget in LEVELS:
        g = groups[budget]
        if not g:
            print(f"{label} | 미실행"); continue
        k, exact = n_correct(g), n_correct(g, tol=1e-9)
        lo, hi = wilson(k, len(g))
        c = means[budget]
        print(f"{label} | {len(g)} | {st.mean(r['thoughts'] for r in g):.2f} | "
              f"{st.mean(r['cands'] for r in g):.2f} | {c['actual']:.8f} | "
              f"{c['actual']/means[None]['actual']:.2f}× | {c['legacy']/means[None]['legacy']:.2f}× | "
              f"{k}/{len(g)} [{lo:.1%}, {hi:.1%}] | {exact}/{len(g)}")
    if -1 in means:
        for ref in (None, 0):
            if ref not in means: continue
            print(f"자동 / {ref!r}: actual {means[-1]['actual']/means[ref]['actual']:.2f}×; "
                  f"legacy {means[-1]['legacy']/means[ref]['legacy']:.2f}×")
        print("같은 허용오차 통과 횟수는 일반 정확도의 동등성 증명이 아니다.")
    active = [r for r in ok if r['thoughts'] > 0]
    if active:
        share = sum(r['thoughts'] for r in active) / sum(r['thoughts']+r['cands'] for r in active)
        print(f"사고 발생 행의 합계 기준 사고/출력계 = {share:.3%} (행별 비율의 평균과 다름)")
    if groups[512]:
        th = [r['thoughts'] for r in groups[512]]
        print(f"512 조건 STOP 행의 사고량 {min(th)}–{max(th)}; 예산 절단이 오답 원인이라고 확인하지 않음.")
    print("새 live 실행은 유료이며 모델·설정·시점에 따라 달라질 수 있다.")
    print('='*100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--model", default="gemini-3.1-flash-lite")
    ap.add_argument("--sleep", type=float, default=1.5)
    ap.add_argument("--out", default="results/thinking_sweep_new.jsonl")
    ap.add_argument("--summarize", metavar="PATH")
    ap.add_argument("--allow-legacy-budget", action="store_true",
                    help="explicit opt-in to historical thinkingBudget requests; unsupported by current Gemini 3 docs")
    args = ap.parse_args()
    if args.summarize:
        summarize(args.summarize)
    else:
        if args.n < 1:
            ap.error("--n must be positive")
        if args.model.startswith("gemini-3") and not args.allow_legacy_budget:
            ap.error("Current Gemini 3 docs use thinkingLevel, not this historical budget sweep. Use exp10 or explicitly --allow-legacy-budget; no result is pre-confirmed.")
        run(args)


if __name__ == "__main__":
    main()
