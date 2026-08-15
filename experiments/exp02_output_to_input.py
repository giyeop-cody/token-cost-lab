# -*- coding: utf-8 -*-
"""
실험 02 — 출력 토큰을 입력 토큰으로 환전하기 (주장 ③·④·⑤ 검증)

무엇을 재는가:
  (1) 모델별 출력/입력 단가 배수
  (2) "대충 시키고 되묻기" vs "스펙을 붙여넣고 한 방에" 두 워크플로의 비용
  (3) 팀 규모로 확대했을 때의 연간 차액
  (4) 손익분기: 출력 1토큰을 줄이려면 입력을 몇 토큰까지 더 써도 남는가

실행:
  python experiments/exp02_output_to_input.py
  python experiments/exp02_output_to_input.py --model gpt5 --devs 20

출처:
  단가는 lab/pricing.py (2026-08 벤더 공개 리스트 기준).
    Anthropic  — https://www.anthropic.com/pricing
    OpenAI     — https://openai.com/api/pricing
    Google     — https://ai.google.dev/pricing
    DeepSeek   — https://api-docs.deepseek.com/quick_start/pricing
  워크플로별 토큰 수는 측정값이 아니라 전형값 가정이다.
  실제 청구 토큰을 보려면 exp08_gemini_live.py 를 쓸 것.
  전체 목록: ../SOURCES.md
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab import pricing, report  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet", choices=list(pricing.MODELS))
    ap.add_argument("--devs", type=int, default=10, help="팀 인원")
    ap.add_argument("--tasks-per-day", type=int, default=8)
    ap.add_argument("--workdays", type=int, default=22)
    args = ap.parse_args()

    m = pricing.get(args.model)

    report.title("실험 02 — 출력 토큰을 입력 토큰으로 환전하기 (주장 ③·④·⑤)")

    report.section("A. 출력은 입력보다 몇 배 비싼가")
    rows = [[mm.name, f"${mm.inp:g}", f"${mm.out:g}", f"{mm.ratio:.1f}x",
             f"{mm.cache_read:g}x", f"{mm.out/(mm.inp*mm.cache_read):.0f}x"]
            for mm in pricing.MODELS.values()]
    report.table(
        ["모델", "입력/1M", "출력/1M", "출력÷입력", "캐시읽기", "출력÷캐시입력"],
        rows, ["l", "r", "r", "r", "r", "r"],
    )
    print("  → 출력은 입력의 2~8배. 캐시된 입력과 비교하면 최대 50배 차이가 난다.")
    print("  이유: 입력은 한 번에 병렬 prefill, 출력은 한 토큰씩 순차 decode.")

    report.section(f"B. 두 워크플로의 비용 — {m.name}")
    scenarios = [
        ("A. 대충 지시 + 되묻기 루프",
         "한 줄 지시 → 모델이 길게 추론 → 확인 질문 → 재작업",
         2_000, 12_000),
        ("B. 웹에서 정리 → 스펙 주입",
         "정리된 스펙/제약/수용조건을 입력으로 붙여넣고 실행만 시킴",
         6_000, 3_000),
    ]
    rows = []
    base = None
    for name, desc, i, o in scenarios:
        c = pricing.cost(m, i, o)
        base = base or c
        rows.append([name, f"{i:,}", f"{o:,}", pricing.usd(c),
                     "기준" if c == base else f"{(c/base-1)*100:+.0f}%"])
    report.table(["시나리오", "입력tok", "출력tok", "요청당 비용", "차이"],
                 rows, ["l", "r", "r", "r", "r"])
    a = pricing.cost(m, 2_000, 12_000)
    b = pricing.cost(m, 6_000, 3_000)
    save = (1 - b / a) * 100
    print(f"  → 입력을 3배로 늘렸는데 총비용은 {save:.0f}% 줄었다.")
    print("     출력 토큰이 비용의 대부분을 차지하기 때문이다.")

    report.section("C. 팀 단위로 확대하면")
    n = args.devs * args.tasks_per_day * args.workdays
    ya, yb = a * n * 12, b * n * 12
    report.kv("월 요청 수",
              f"{n:,}건", f"({args.devs}명 x {args.tasks_per_day}건/일 x {args.workdays}일)")
    report.kv("A 워크플로 월/연", f"{pricing.usd(a*n,2)} / {pricing.usd(ya,0)}")
    report.kv("B 워크플로 월/연", f"{pricing.usd(b*n,2)} / {pricing.usd(yb,0)}")
    report.kv("연간 절감액", pricing.usd(ya - yb, 0), f"({save:.0f}%)")

    report.section("D. 손익분기 — 입력을 얼마나 더 써도 되는가")
    print(f"  {m.name} 기준, 출력 1토큰 = 입력 {m.ratio:.1f}토큰과 같은 값.")
    for cut in (500, 1_000, 3_000, 5_000):
        print(f"    출력 {cut:,}토큰을 줄일 수 있다면 "
              f"→ 입력을 {int(cut*m.ratio):,}토큰까지 더 써도 본전.")
    print(f"  캐시에 올린 입력이라면 여유는 {m.ratio/m.cache_read:,.0f}배로 커진다 "
          f"(출력 1,000tok ↔ 캐시입력 {int(1000*m.ratio/m.cache_read):,}tok).")
    print("  → '스펙을 길게 쓰면 입력이 늘어서 손해 아닌가?' 라는 반론에 대한 답이다.")

    report.section("E. 언어 선택이 thinking 비용에 미치는 영향")
    print("  실험 01에서 측정한 배수를 thinking 토큰에 그대로 적용한다.")
    rows = []
    for ratio, label in [(1.00, "영어 사고"), (1.44, "한국어 사고 (o200k 실측)"),
                         (1.88, "한국어 사고 (Claude 토크나이저, 외부 실측)")]:
        for th in (4_000, 8_000, 16_000):
            pass
        c8 = int(8_000 * ratio) * m.out / 1e6
        rows.append([label, f"{int(8_000*ratio):,}", pricing.usd(c8),
                     f"{(ratio-1)*100:+.0f}%"])
    report.table(["사고 언어", "thinking tok", "요청당 비용", "추가 비용"],
                 rows, ["l", "r", "r", "r"])
    extra = (int(8_000 * 1.44) - 8_000) * m.out / 1e6 * n * 12
    report.kv("한국어 사고의 연간 추가 비용", pricing.usd(extra, 0),
              f"(위 {n:,}건/월 기준, thinking 8K tok 가정)")

    report.verdict(
        "③·⑤ 출력이 입력보다 비싸므로, 출력을 입력으로 환전하라",
        "참",
        f"{m.name}에서 입력 3배 증가를 감수하고도 총비용 {save:.0f}% 절감. "
        f"손익분기상 출력 1토큰당 입력 {m.ratio:.1f}토큰(캐시 시 "
        f"{m.ratio/m.cache_read:.0f}토큰)까지 허용된다.",
    )
    print("\n  ⚠️ 한계: 위 토큰 수치는 전형적인 값을 가정한 시뮬레이션이다.")
    print("     자기 팀의 실제 usage 로그를 넣어 다시 돌려야 의미가 있다.")


if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
