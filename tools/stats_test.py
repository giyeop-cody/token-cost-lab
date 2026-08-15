#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stats_test.py — 라이브 벤치 결과에 통계 검정을 붙인다.

"평균이 다르다"는 것만으로는 근거가 약하다. 표본이 작으면 우연히 갈릴 수 있고,
실제로 이 프로젝트에서는 N=5와 N=100의 결론이 부호까지 뒤집힌 적이 있다.
그래서 다음을 계산한다.

  · 부트스트랩 95% 신뢰구간 (분포 가정 없음, 표준라이브러리만 사용)
  · Welch t 검정 근사 p값 (등분산 가정 없음)
  · Cliff's delta (비모수 효과크기 — 두 분포가 실제로 얼마나 겹치는가)
  · 글자수 정규화 비용 ($/1,000자) — 분량을 통제한 진짜 비교

사용:
    python tools/stats_test.py results/live_lang.jsonl
    python tools/stats_test.py results/live_lang_thinking.jsonl --label 사고켬
"""
import argparse
import json
import math
import random
import statistics as st

IN_R, OUT_R = 1.25 / 1e6, 10.0 / 1e6


def cost(r):
    return r["prompt"] * IN_R + (r["thoughts"] + r["cands"]) * OUT_R


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
    """비율(mean_a / mean_b)의 신뢰구간 — 1.0을 포함하면 유의하지 않다."""
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


def _norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def fmt_p(p):
    """정규근사에서 p가 언더플로로 0.0이 되는 경우를 정직하게 표기한다.
    'p = 0'은 수학적으로 틀린 말이다 — 계산 한계임을 밝힌다."""
    if p != p:
        return "nan"
    if p <= 0.0:
        return "< 1e-16 (정규근사 한계)"
    return f"{p:.2e}"


def welch(a, b):
    """Welch t 검정. 자유도가 크므로 정규근사로 p값을 낸다."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan"), float("nan")
    va, vb = st.variance(a), st.variance(b)
    se = math.sqrt(va / na + vb / nb)
    if se == 0:
        return float("nan"), float("nan")
    t = (st.mean(a) - st.mean(b)) / se
    p = 2 * (1 - _norm_cdf(abs(t)))
    return t, p


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
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.path, encoding="utf-8")]
    ok = [r for r in rows if "error" not in r and r.get("finish") in ("STOP", "")]

    hdr = f"통계 검정 — {args.path}"
    if args.label:
        hdr += f"  [{args.label}]"
    print("=" * 84)
    print(f"  {hdr}")
    print(f"  표본 {len(rows)}건 중 유효 {len(ok)}건")
    print("=" * 84)

    for task in sorted({r["task"] for r in ok}):
        en = [r for r in ok if r["task"] == task and r["lang"] == "en"]
        ko = [r for r in ok if r["task"] == task and r["lang"] == "ko"]
        if not en or not ko:
            continue
        print(f"\n── 과제: {task}  (EN n={len(en)} · KO n={len(ko)}) " + "─" * 34)

        ce, ck = [cost(r) for r in en], [cost(r) for r in ko]
        me, mk = st.mean(ce), st.mean(ck)
        lo, hi = boot_ratio_ci(ck, ce)
        t, p = welch(ck, ce)
        d, mag = cliffs_delta(ck, ce)

        print(f"  [A] 호출당 비용")
        print(f"      EN ${me:.6f}  ·  KO ${mk:.6f}  ·  비율 {mk/me:.3f}×")
        print(f"      비율 95% CI  [{lo:.3f}, {hi:.3f}]"
              f"   {'← 1.0 포함: 유의하지 않음' if lo <= 1.0 <= hi else '← 유의함'}")
        print(f"      Welch p = {fmt_p(p)}   ·   Cliff's δ = {d:+.3f} ({mag})")

        # 분량 정규화 — 진짜 비교
        ne = [cost(r) / r["chars"] * 1000 for r in en if r.get("chars")]
        nk = [cost(r) / r["chars"] * 1000 for r in ko if r.get("chars")]
        if ne and nk:
            mne, mnk = st.mean(ne), st.mean(nk)
            nlo, nhi = boot_ratio_ci(nk, ne)
            nt, np_ = welch(nk, ne)
            nd, nmag = cliffs_delta(nk, ne)
            print(f"  [B] 분량 정규화 ($/1,000자) ← 결론은 이쪽")
            print(f"      EN ${mne:.5f}  ·  KO ${mnk:.5f}  ·  비율 {mnk/mne:.2f}×")
            print(f"      비율 95% CI  [{nlo:.2f}, {nhi:.2f}]"
                  f"   {'← 1.0 포함: 유의하지 않음' if nlo <= 1.0 <= nhi else '← 유의함'}")
            print(f"      Welch p = {fmt_p(np_)}   ·   Cliff's δ = {nd:+.3f} ({nmag})")
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
    print("  발표에서 인용할 값은 [B] 분량 정규화 비율이다.")
    print("=" * 84)


if __name__ == "__main__":
    main()
