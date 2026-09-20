#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stats_test.py — 라이브 벤치 결과에 통계 검정을 붙인다.

"평균이 다르다"는 것만으로는 근거가 약하다. 표본이 작으면 우연히 갈릴 수 있고,
과거 예비 서술에는 결론 변화가 있으나 N=5/N=100 원자료는 현재 미포함이다.
그래서 다음을 계산한다.

  · 부트스트랩 95% 신뢰구간 (분포 가정 없음, 표준라이브러리만 사용)
  · Welch–Satterthwaite t 검정 p값 (등분산 가정 없음)
  · Cliff's delta (비모수 효과크기 — 두 분포가 실제로 얼마나 겹치는가)
  · 글자수 정규화 비용 ($/1,000자) — 문자 단위 지표 (언어 간 의미량을 통제하지 않음)

사용:
    python tools/stats_test.py results/live_lang_thinking.jsonl
    python tools/stats_test.py results/live_lang_thinking.jsonl --label 사고켬
"""
import argparse
import json
import math
import random
import statistics as st

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scipy.stats import t as t_dist
from lab.pricing import log_cost


def cost(r, basis="actual"):
    return log_cost(r, basis)


def boot_ci(vals, iters=20000, alpha=0.05, seed=42):
    """평균의 부트스트랩 신뢰구간."""
    rnd = random.Random(seed)
    n = len(vals)
    means = []
    for _ in range(iters):
        means.append(sum(rnd.choice(vals) for _ in range(n)) / n)
    means.sort()
    lo = means[int(iters * alpha / 2)]
    hi = means[int(iters * (1 - alpha / 2))]
    return lo, hi


def boot_ratio_ci(a, b, iters=20000, alpha=0.05, seed=42):
    """비율(mean_a / mean_b)의 percentile bootstrap 구간. Welch 검정과 별개다."""
    rnd = random.Random(seed)
    na, nb = len(a), len(b)
    out = []
    for _ in range(iters):
        ma = sum(rnd.choice(a) for _ in range(na)) / na
        mb = sum(rnd.choice(b) for _ in range(nb)) / nb
        if mb:
            out.append(ma / mb)
    out.sort()
    return out[int(len(out) * alpha / 2)], out[int(len(out) * (1 - alpha / 2))]


def fmt_p(p):
    if not math.isfinite(p):
        return "nan (not estimable)"
    return f"{p:.2e}" if p > 0 else "below floating-point resolution"


def welch_details(a, b):
    """Two-sided Welch test; unequal variances, estimated (not infinite) df."""
    if len(a) < 2 or len(b) < 2:
        return (float("nan"),) * 3
    sa, sb = st.variance(a) / len(a), st.variance(b) / len(b)
    if sa + sb == 0:
        return (float("nan"),) * 3  # do not invent significance for constants
    t = (st.mean(a) - st.mean(b)) / math.sqrt(sa + sb)
    df = (sa + sb) ** 2 / (sa ** 2 / (len(a) - 1) + sb ** 2 / (len(b) - 1))
    p = 2 * t_dist.sf(abs(t), df)  # survival function avoids 1-CDF cancellation
    return t, float(p), df


def welch(a, b):
    return welch_details(a, b)[:2]


def cliffs_delta(a, b):
    """비모수 효과크기. |d| 0.147 작음 / 0.33 중간 / 0.474 큼."""
    gt = lt = 0
    for x in a:
        for y in b:
            if x > y:
                gt += 1
            elif x < y:
                lt += 1
    n = len(a) * len(b)
    d = (gt - lt) / n if n else 0.0
    mag = ("무시할만함", "작음", "중간", "큼")[
        sum(abs(d) >= t for t in (0.147, 0.33, 0.474))]
    return d, mag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--label", default="")
    ap.add_argument("--price-basis", choices=["actual", "legacy"], default="actual")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.path, encoding="utf-8")]
    ok = [r for r in rows if "error" not in r and r.get("finish") == "STOP"]

    hdr = f"통계 검정 — {args.path}"
    if args.label:
        hdr += f"  [{args.label}]"
    print("=" * 84)
    print(f"  {hdr}")
    print(f"  표본 {len(rows)}건 중 STOP {len(ok)}건; 제외 {len(rows)-len(ok)}건")
    print(f"  단가 기준: {args.price_basis} (actual=모델별 Standard 2026-09-20; legacy=발표 환산)")
    print("  반복 호출의 조건부 비교; 과제 다양성·언어별 품질·추론 깊이는 검증하지 않음")
    print("=" * 84)

    for task in sorted({r["task"] for r in ok}):
        en = [r for r in ok if r["task"] == task and r["lang"] == "en"]
        ko = [r for r in ok if r["task"] == task and r["lang"] == "ko"]
        if not en or not ko:
            continue
        print(f"\n── 과제: {task}  (EN n={len(en)} · KO n={len(ko)}) " + "─" * 34)

        ce, ck = [cost(r, args.price_basis) for r in en], [cost(r, args.price_basis) for r in ko]
        me, mk = st.mean(ce), st.mean(ck)
        lo, hi = boot_ratio_ci(ck, ce)
        t, p, df = welch_details(ck, ce)
        d, mag = cliffs_delta(ck, ce)

        print(f"  [A] 호출당 비용")
        print(f"      EN ${me:.6f}  ·  KO ${mk:.6f}  ·  비율 {mk/me:.3f}×")
        print(f"      비율 95% CI  [{lo:.3f}, {hi:.3f}]"
              f"   {'← 1.0 포함: 유의하지 않음' if lo <= 1.0 <= hi else '← 유의함'}")
        print(f"      Welch t={t:.3f}, df={df:.3f}, p = {fmt_p(p)}   ·   Cliff's δ = {d:+.3f} ({mag})")

        # 문자 단위 기술통계 — 의미량·품질의 정규화가 아님
        ne = [cost(r, args.price_basis) / r["chars"] * 1000 for r in en if r.get("chars")]
        nk = [cost(r, args.price_basis) / r["chars"] * 1000 for r in ko if r.get("chars")]
        if ne and nk:
            mne, mnk = st.mean(ne), st.mean(nk)
            nlo, nhi = boot_ratio_ci(nk, ne)
            nt, np_, ndf = welch_details(nk, ne)
            nd, nmag = cliffs_delta(nk, ne)
            print(f"  [B] 문자 단위 비용 ($/1,000자) — 동일 의미량 비교 아님")
            print(f"      EN ${mne:.5f}  ·  KO ${mnk:.5f}  ·  비율 {mnk/mne:.2f}×")
            print(f"      비율 95% CI  [{nlo:.2f}, {nhi:.2f}]"
                  f"   {'← 1.0 포함: 유의하지 않음' if nlo <= 1.0 <= nhi else '← 유의함'}")
            print(f"      Welch t={nt:.3f}, df={ndf:.3f}, p = {fmt_p(np_)}   ·   Cliff's δ = {nd:+.3f} ({nmag})")
            print(f"      실제 쓴 글자: EN {st.mean(r['chars'] for r in en):.0f}자"
                  f"  ·  KO {st.mean(r['chars'] for r in ko):.0f}자"
                  f"  (KO/EN {st.mean(r['chars'] for r in ko)/st.mean(r['chars'] for r in en):.2f}×)")

        th_en = st.mean(r["thoughts"] for r in en)
        th_ko = st.mean(r["thoughts"] for r in ko)
        if th_en or th_ko:
            tlo, thi = boot_ratio_ci([r["thoughts"] for r in ko],
                                     [r["thoughts"] for r in en])
            print(f"  [C] 사고 토큰  EN {th_en:.0f}  ·  KO {th_ko:.0f}"
                  f"  ·  비율 {th_ko/max(th_en,1):.2f}×"
                  f"  95% CI [{tlo:.2f}, {thi:.2f}]")
            print(f"      출력 토큰 중 사고 비중:"
                  f"  EN {th_en/(th_en+st.mean(r['cands'] for r in en))*100:.0f}%"
                  f"  ·  KO {th_ko/(th_ko+st.mean(r['cands'] for r in ko))*100:.0f}%")

    print("\n" + "=" * 84)
    print("  해석 규칙: 비율의 95% 신뢰구간이 1.0을 포함하면 '차이 없음'을 배제할 수 없다.")
    print("  [A]와 [B]는 다른 질문의 답이다. 한 문제 반복의 유의성은 언어 일반 우위가 아니다.")
    print("=" * 84)


if __name__ == "__main__":
    main()
