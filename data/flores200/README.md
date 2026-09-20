# FLORES-200 — aligned English / Korean devtest subset

Attribution: **NLLB Team et al. (2022), No Language Left Behind: Scaling
Human-Centered Machine Translation**, Meta AI / FLORES-200 contributors.

- Dataset: https://github.com/facebookresearch/flores/tree/main/flores200
- Source archive: https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz
- Archive SHA-256: `b8b0b76783024b85797e5cc75064eb83fc5288b41e9654dabc7be6ae944011f6`
- Retrieved: 2026-09-20. `devtest/eng_Latn.devtest` and
  `devtest/kor_Hang.devtest` are reproduced byte-for-byte (1,012 aligned rows).
- **Data license: CC-BY-SA 4.0**, not this repository's MIT code license.
  License: https://creativecommons.org/licenses/by-sa/4.0/
  Legal terms: https://creativecommons.org/licenses/by-sa/4.0/legalcode
  Upstream declaration: https://github.com/facebookresearch/flores#licenses
- No text changes. Only these two files were selected from the larger archive.
- Reproduce: `python tools/parallel_tokenizer_bench.py`. It strips line separators,
  not spaces or Unicode content. File hashes, package version and per-pair counts
  are in `results/flores_tokenizers.json` and `.jsonl`.

대응 번역 코퍼스의 로컬 인코딩 실측입니다. Gemini/Claude 토큰 수,
실제 생성 비용, 추론 정확도 또는 모든 도메인의 효과를 측정한 것이 아닙니다.
