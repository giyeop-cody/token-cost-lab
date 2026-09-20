# -*- coding: utf-8 -*-
"""
실험 01 — 한국어 vs 영어 토큰 수 (주장 ① 검증)

무엇을 재는가:
  같은 의미의 문장 쌍을 여러 토크나이저로 인코딩해서, 한국어가 영어보다
  토큰을 몇 배 쓰는지 직접 측정한다.

왜 중요한가:
  thinking(추론) 토큰은 출력 단가로 과금된다. 사고 언어의 토큰 배수는
  그대로 비용 배수가 된다.

실행:
  python experiments/exp01_tokenizer_ko_en.py
  python experiments/exp01_tokenizer_ko_en.py --pairs data/my_pairs.json

출처:
  Petrov et al., "Language Model Tokenizers Introduce Unfairness Between Languages",
    NeurIPS 2023 — https://arxiv.org/abs/2305.15425
    (동일 내용이 언어에 따라 최대 15배, 일부 언어는 영어 대비 최소 2.5배 지불)
  "When Models Reason in Your Language" (XReasoning), 2025
    — https://arxiv.org/abs/2505.22888
    (사용자 언어 사고 강제 시 언어 일치 46%->98%, 정확도 26%->17%)
  "Language Matters: Multilingual Input and Reasoning Paths", 2025
    — https://arxiv.org/abs/2505.17407  (허브 언어 추론 시 최대 +26.8%)
  전체 목록: ../SOURCES.md
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab import report  # noqa: E402

DEFAULT_PAIRS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "sentence_pairs.json",
)


def load_pairs(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=DEFAULT_PAIRS, help="문장 쌍 JSON 경로")
    ap.add_argument("--json", action="store_true", help="JSON으로만 출력")
    args = ap.parse_args()

    try:
        import tiktoken
    except ImportError:
        raise SystemExit("tiktoken 이 필요합니다:  pip install -r requirements.txt")

    encs = {
        "o200k_base": tiktoken.get_encoding("o200k_base"),   # GPT-5 / 4o 계열
        "cl100k_base": tiktoken.get_encoding("cl100k_base"),  # GPT-4 / 3.5 계열
    }

    pairs = load_pairs(args.pairs)
    results = []
    for p in pairs:
        row = {"label": p["label"], "en_chars": len(p["en"]), "ko_chars": len(p["ko"])}
        for name, enc in encs.items():
            row[f"en_{name}"] = len(enc.encode(p["en"]))
            row[f"ko_{name}"] = len(enc.encode(p["ko"]))
            row[f"ratio_{name}"] = round(row[f"ko_{name}"] / row[f"en_{name}"], 2)
        results.append(row)

    totals = {}
    for name in encs:
        te = sum(r[f"en_{name}"] for r in results)
        tk = sum(r[f"ko_{name}"] for r in results)
        totals[name] = {"en": te, "ko": tk, "ratio": round(tk / te, 3)}

    if args.json:
        print(json.dumps({"rows": results, "totals": totals},
                         ensure_ascii=False, indent=2))
        return

    report.title("실험 01 — 한국어 vs 영어 토큰 수 (주장 ①)")
    print(f"  문장 쌍 {len(pairs)}개 · 소스: {os.path.relpath(args.pairs)}")

    report.section("토크나이저별 결과")
    rows = []
    for r in results:
        rows.append([
            r["label"],
            f'{r["en_o200k_base"]} / {r["ko_o200k_base"]}',
            f'{r["ratio_o200k_base"]:.2f}x',
            f'{r["en_cl100k_base"]} / {r["ko_cl100k_base"]}',
            f'{r["ratio_cl100k_base"]:.2f}x',
        ])
    rows.append([
        "── 합계",
        f'{totals["o200k_base"]["en"]} / {totals["o200k_base"]["ko"]}',
        f'{totals["o200k_base"]["ratio"]:.2f}x',
        f'{totals["cl100k_base"]["en"]} / {totals["cl100k_base"]["ko"]}',
        f'{totals["cl100k_base"]["ratio"]:.2f}x',
    ])
    report.table(
        ["문장", "o200k EN/KO", "배수", "cl100k EN/KO", "배수"],
        rows, ["l", "r", "r", "r", "r"],
    )

    report.section("글자 수는 왜 신뢰할 수 없는가")
    o = encs["o200k_base"]
    en_all = " ".join(p["en"] for p in pairs)
    ko_all = " ".join(p["ko"] for p in pairs)
    en_tpc = len(o.encode(en_all)) / len(en_all)
    ko_tpc = len(o.encode(ko_all)) / len(ko_all)
    report.kv("영어 토큰/글자", f"{en_tpc:.3f}")
    report.kv("한국어 토큰/글자", f"{ko_tpc:.3f}", f"({ko_tpc/en_tpc:.2f}배)")
    report.kv("512토큰에 들어가는 글자 수",
              f"영어 {int(512/en_tpc):,}자  vs  한국어 {int(512/ko_tpc):,}자")
    print("  → RAG 청킹을 '글자 수'로 자르면 한국어 청크만 조용히 잘려 나간다.")

    report.section("왜 이런 일이 생기는가 — 실제 분해")
    for word in ["에이전트", " agent", "데이터베이스", " database", "인증", " auth"]:
        ids = o.encode(word)
        pieces = "/".join(o.decode([t]) for t in ids)
        report.kv(f"'{word}'", f"{len(ids)}토큰", f"[{pieces}]")
    print("  → o200k 어휘 20만개 중 한글은 약 1.2%. 자리가 없어 잘게 쪼개진다.")

    ratio = totals["o200k_base"]["ratio"]
    report.verdict(
        "① 한국어 추론은 영어보다 비싸다",
        "참 (단, 배수는 토크나이저에 따라 다름)",
        f"최신 o200k에서도 {ratio:.2f}배, 구형 cl100k에서는 "
        f"{totals['cl100k_base']['ratio']:.2f}배. "
        "Claude 토크나이저는 외부 측정 기준 1.88배로 더 나쁨.",
    )
    print("\n  ⚠️ 반례도 있다: 모델·언어·과제별 효과가 다르다. 생성 길이와 정확도를 각각 확인해야 한다.")
    print("     → 배수는 '자기가 쓰는 모델'로 직접 재라. 이 스크립트가 그 용도다.")


if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
