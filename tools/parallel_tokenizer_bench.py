#!/usr/bin/env python3
"""FLORES-200 devtest 1,012 aligned EN/KO pairs: local tokenizer measurement.

No model generation, hidden reasoning or billed API usage is measured here.
Newline separators are excluded; Unicode text is otherwise unchanged. Ratios
are ratios of token sums, not averages of sentence ratios.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "flores200"


def measure(data_dir=DATA):
    files = {"en": data_dir / "eng_Latn.devtest", "ko": data_dir / "kor_Hang.devtest"}
    texts = {lang: path.read_text(encoding="utf-8").splitlines() for lang, path in files.items()}
    if len(texts["en"]) != 1012 or len(texts["ko"]) != 1012:
        raise ValueError("Expected exactly 1,012 aligned devtest sentences per language")
    rows = [{"id": i + 1, "en_chars": len(en), "ko_chars": len(ko)}
            for i, (en, ko) in enumerate(zip(texts["en"], texts["ko"]))]
    result = {
        "evidence_type": "local_tokenizer_measurement",
        "dataset": "FLORES-200 devtest eng_Latn / kor_Hang",
        "source": "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz",
        "archive_sha256": "b8b0b76783024b85797e5cc75064eb83fc5288b41e9654dabc7be6ae944011f6",
        "input_sha256": {lang: hashlib.sha256(path.read_bytes()).hexdigest() for lang, path in files.items()},
        "n_pairs": 1012,
        "tiktoken_version": importlib.metadata.version("tiktoken"),
        "chars": {lang: sum(map(len, lines)) for lang, lines in texts.items()},
        "tokenizers": {},
    }
    result["ko_en_char_ratio"] = result["chars"]["ko"] / result["chars"]["en"]
    for name in ("o200k_base", "cl100k_base"):
        enc = tiktoken.get_encoding(name)
        counts = {lang: [len(enc.encode(t)) for t in lines] for lang, lines in texts.items()}
        totals = {lang: sum(ns) for lang, ns in counts.items()}
        result["tokenizers"][name] = {**totals, "ko_en_ratio": totals["ko"] / totals["en"]}
        for i, row in enumerate(rows):
            row[name] = {lang: values[i] for lang, values in counts.items()}
    return result, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "flores_tokenizers.json")
    ap.add_argument("--rows", type=Path, default=ROOT / "results" / "flores_tokenizers.jsonl")
    args = ap.parse_args()
    result, rows = measure()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.rows.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
