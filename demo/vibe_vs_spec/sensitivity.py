# -*- coding: utf-8 -*-
"""실험 E — 단가비 민감도 분석: Spec의 -8.3%는 어디까지 일반화되는가.

질문:
  Vibe→Spec에서 토큰은 [입력 +666, 추론 -260, 출력 -420, 캐시 +156] 이동했다.
  이 이동이 비용 절감이 되는 조건은? 입력:출력 단가비(r)가 얼마 이상이어야 하는가?

모델:
  cost = in·p_in + (reason+out)·p_out + cache·(0.1·p_in)
  (추론은 출력 요율 과금, 캐시 읽기는 입력의 1/10 — 업계 표준 관행)

손익분기:
  Δcost = 666·p_in − 680·p_out + 156·(0.1·p_in) = 681.6·p_in − 680·p_out
  Spec 승리 ⟺ p_out/p_in > 681.6/680 ≈ 1.0024

실행:
  python demo/vibe_vs_spec/sensitivity.py
"""
import json
from pathlib import Path

# ---- 실측 사용량 (usage.json과 동일) ----
VIBE = dict(inp=486, rea=1240, out=5830, cac=312)
SPEC = dict(inp=1152, rea=980, out=5410, cac=468)

# ---- 공개 리스트 단가 (per 1M tokens, 2026-08 확인. 캐시읽기=입력의 1/10 가정) ----
MODELS = {
    "GPT-5":             (1.25, 10.00),
    "Claude Sonnet 4.5": (3.00, 15.00),
    "Claude Opus 4":     (5.00, 25.00),
    "Claude Haiku 4.5":  (1.00,  5.00),
    "Gemini 2.5 Pro":    (1.25, 10.00),
    "DeepSeek-chat":     (0.27,  1.10),
}


def cost(u, p_in, p_out):
    return (u["inp"] * p_in + (u["rea"] + u["out"]) * p_out + u["cac"] * 0.1 * p_in) / 1e6


def main():
    print("=" * 74)
    print("실험 E — 단가비 민감도: Spec 절감폭은 입력:출력 단가비의 함수다")
    print("=" * 74)

    # 1) 손익분기점 (해석적)
    d_in = SPEC["inp"] - VIBE["inp"]                          # +666
    d_exp = (SPEC["rea"] + SPEC["out"]) - (VIBE["rea"] + VIBE["out"])  # -680
    d_cac = SPEC["cac"] - VIBE["cac"]                          # +156
    breakeven = (d_in + 0.1 * d_cac) / -d_exp
    print(f"\n토큰 이동: 입력 {d_in:+}, 추론+출력 {d_exp:+}, 캐시 {d_cac:+}")
    print(f"손익분기 단가비 r* = p_out/p_in = {breakeven:.4f}")
    print("→ 출력 단가가 입력 단가보다 0.24%만 높아도 Spec이 이긴다.")
    print("→ 알려진 모든 상용 모델은 r ≥ 3.7 이므로, 이 토큰 이동에서 Spec은 항상 승리.\n")

    # 2) 단가비 스윕
    print(f"{'단가비 r':>8} | {'절감률':>8}   (p_in=1 고정, r = p_out/p_in)")
    print("-" * 40)
    for r in [1, 2, 3, 5, 8, 12, 16, 1000]:
        v = cost(VIBE, 1, r); s = cost(SPEC, 1, r)
        label = f"1:{r}" if r < 1000 else "1:∞"
        print(f"{label:>8} | {(s / v - 1) * 100:+7.2f}%")
    asym = (d_exp) / (VIBE["rea"] + VIBE["out"])
    print(f"\n점근선(출력 지배 극한): {asym * 100:+.2f}%  — 절감률은 -9.6%에 수렴, 그 이상은 불가능")

    # 3) 실제 모델 대입
    print(f"\n{'모델':<20} | {'r':>5} | {'Vibe':>9} | {'Spec':>9} | {'차이':>7}")
    print("-" * 62)
    rows = {}
    for name, (pi, po) in MODELS.items():
        v = cost(VIBE, pi, po); s = cost(SPEC, pi, po)
        d = (s / v - 1) * 100
        rows[name] = dict(ratio=round(po / pi, 1), vibe_usd=round(v, 5),
                          spec_usd=round(s, 5), delta_pct=round(d, 1))
        print(f"{name:<20} | {po / pi:>5.1f} | ${v:>8.5f} | ${s:>8.5f} | {d:+6.1f}%")

    print("\n결론:")
    print("  1. 이 케이스의 토큰 이동(싼 입력↑, 비싼 추론·출력↓)은 사실상 모든 단가 체계에서 흑자.")
    print("  2. 절감률은 단가비가 클수록 커지지만 -9.6%가 상한 (출력 감소분 -680/7070의 극한).")
    print("  3. 더 큰 절감은 단가비가 아니라 '재작업 턴 수 감소'에서 나온다 → EXPERIMENT_A_PROTOCOL.md")

    out = Path(__file__).parent / "sensitivity_results.json"
    out.write_text(json.dumps({
        "breakeven_ratio": round(breakeven, 4),
        "asymptote_pct": round(asym * 100, 2),
        "models": rows,
    }, ensure_ascii=False, indent=2))
    print(f"\n저장: {out.name}")


if __name__ == "__main__":
    main()
