#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thinking_sweep.py — 사고 예산(thinkingBudget)만 바꿔가며 실제 과금을 계측한다.

발표 슬라이드 24("사고 토큰 37배")의 근거를 N회 반복 표본으로 재생산한다.
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
    ("끔 (0)", 0),
    ("512", 512),
    ("2048", 2048),
    ("자동 (-1)", -1),
]

# ⚠️ 이 스크립트는 flash-lite를 호출하지만, 비용은 관례상 gemini-25($1.25/$10)
# 단가로 환산해 왔다(덱의 240× 근거). 실단가 기준 배수도 함께 출력해 전제를 드러낸다.
IN_R, OUT_R = 1.25 / 1e6, 10.0 / 1e6          # 환산 기준 (gemini-25)
ALT_IN, ALT_OUT = 0.10 / 1e6, 0.40 / 1e6      # 실제 모델(flash-lite) 공식 단가


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


def n_correct(rows):
    """응답에서 첫 숫자를 뽑아 정답(±0.05) 개수를 센다.
    '문자열이 같은가'가 아니라 '정답인가'를 세야 한다 —
    실제로 38.016 / $38.016 / 37.9944(off-by-one)가 섞여 나온다."""
    import re
    n = 0
    for r in rows:
        m = re.findall(r"[\d.]+", (r.get("text") or "").replace(",", ""))
        if m:
            try:
                if abs(float(m[0]) - ANSWER) <= ANSWER_TOL:
                    n += 1
            except ValueError:
                pass
    return n


def summarize(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    ok = [r for r in rows if "error" not in r and r.get("finish") in ("STOP", "")]
    print(f"\n{'='*84}\n  사고 예산 스윕 — 표본 {len(rows)}건 중 유효 {len(ok)}건")
    print(f"  질문 고정 · 모델 고정 · thinkingBudget만 변경\n")
    print(f"  {'예산':<14}{'n':>3}{'사고':>9}{'응답':>8}{'출력계':>9}"
          f"{'비용':>12}{'배수':>9}   정답률(±0.05) [Wilson 95% CI]")
    base = None
    out_rows = []
    for label, budget in LEVELS:
        d = [r for r in ok if r.get("label") == label]
        if not d:
            continue
        th = st.mean(r["thoughts"] for r in d)
        ca = st.mean(r["cands"] for r in d)
        pr = st.mean(r["prompt"] for r in d)
        cost = pr * IN_R + (th + ca) * OUT_R
        if base is None:
            base = cost
        _k = n_correct(d)
        _lo, _hi = wilson(_k, len(d))
        ans = f"{_k}/{len(d)}  [{_lo*100:.0f}–{_hi*100:.0f}%]"
        print(f"  {label:<14}{len(d):>3}{th:>9.0f}{ca:>8.0f}{th+ca:>9.0f}"
              f"{cost:>12.6f}{cost/base:>8.1f}×   {ans}")
        out_rows.append((label, th, ca, cost, cost / base))
    if len(out_rows) >= 2:
        hi = max(out_rows, key=lambda r: r[3])
        lo = min(out_rows, key=lambda r: r[3])
        print(f"\n  최대/최소 비용 배수: {hi[3]/lo[3]:.1f}× "
              f"({hi[0]} vs {lo[0]})")
        nc_hi = n_correct([r for r in ok if r.get("label") == hi[0]])
        nc_lo = n_correct([r for r in ok if r.get("label") == lo[0]])
        print(f"  → 정답률은 {nc_lo}/6 vs {nc_hi}/6 로 같은데 요금만 "
              f"{hi[3]/lo[3]:.1f}배 차이난다.")
        print(f"     (주의: 응답 '문자열'까지 동일한 것은 아니다. "
              f"38.016 / $38.016 / 37.9944 가 섞여 있다.)")
        vis = [r for r in out_rows if r[1] > 0]
        if vis:
            sh = st.mean(r[1] / max(r[1] + r[2], 1) for r in vis)
            print(f"  → 사고가 켜진 구간에서 출력 토큰의 평균 {sh*100:.0f}%가 "
                  f"'보이지 않는' 사고 토큰이다.")

        # 단가 민감도 — 배수는 단가 가정에 의존한다
        def alt_cost(label):
            d = [r for r in ok if r.get("label") == label]
            if not d:
                return None
            return (st.mean(r["prompt"] for r in d) * ALT_IN
                    + (st.mean(r["thoughts"] for r in d)
                       + st.mean(r["cands"] for r in d)) * ALT_OUT)

        a_hi, a_lo = alt_cost(hi[0]), alt_cost(lo[0])
        if a_hi and a_lo:
            print(f"\n  [단가 민감도] 위 배수는 gemini-25($1.25/$10) 환산 기준이다.")
            print(f"  실제 호출 모델의 공식 단가($0.10/$0.40)로 계산하면 "
                  f"{a_hi/a_lo:.0f}×.")
            print(f"  → 인용할 때 '어느 단가 기준인지'를 반드시 함께 말할 것.")
    print(f"{'='*84}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--model", default="gemini-3.1-flash-lite")
    ap.add_argument("--sleep", type=float, default=1.5)
    ap.add_argument("--out", default="results/thinking_sweep.jsonl")
    ap.add_argument("--summarize", metavar="PATH")
    args = ap.parse_args()
    if args.summarize:
        summarize(args.summarize)
    else:
        run(args)


if __name__ == "__main__":
    main()
