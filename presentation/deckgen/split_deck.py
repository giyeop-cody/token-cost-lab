# -*- coding: utf-8 -*-
"""기존 29장 덱을 본편 / 보너스 두 덱으로 분할한다.

build_deck.py 본문을 슬라이드 단위 청크로 잘라, 각 덱에 필요한 청크만
deckkit 헬퍼 위에서 다시 실행한다. 슬라이드 내용 자체는 원본 그대로이므로
분할로 인한 수치 변형이 발생하지 않는다.

    python3 presentation/build/split_deck.py
"""
from __future__ import annotations

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRES = os.path.dirname(HERE)
sys.path.insert(0, HERE)

SRC = os.path.join(HERE, "build_deck.py")

# 원본 청크 번호 → 배분. 주석 번호가 아니라 등장 순서(1-based).
MAIN = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 22, 23, 24, 26, 27, 28, 29]
BONUS = [16, 17, 18, 19, 20, 21, 25]


def load_chunks() -> list[tuple[str, str]]:
    src = io.open(SRC, encoding="utf-8").read()
    body = src[src.index("# ───────────────────────── 1. 표지"):]
    body = body[: body.index("import os as _os")]
    parts = re.split(r"(?m)^(# ─+ .*)$", body)
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]


def run(chunks, order, kit):
    """청크를 deckkit 네임스페이스 위에서 실행한다."""
    ns = {k: getattr(kit, k) for k in dir(kit) if not k.startswith("__")}
    for idx in order:
        head, code = chunks[idx - 1]
        # 원본은 모듈 전역 prs/BLANK를 직접 참조하므로 매번 최신값을 주입
        ns["prs"] = kit.prs
        ns["BLANK"] = kit.BLANK
        # 표지는 slide() 헬퍼를 안 쓰므로 blank_slide()로 치환(카운터는 불변)
        if "prs.slides.add_slide(BLANK)" in code and "slide(" not in code.split("\n")[1]:
            code = code.replace("sl = prs.slides.add_slide(BLANK)", "sl = blank_slide()", 1)
        exec(compile(code, f"<chunk:{head}>", "exec"), ns)
    return kit.prs


def main() -> int:
    import deckkit as kit

    chunks = load_chunks()
    assert len(chunks) == 29, f"청크 {len(chunks)}개 — 원본 구조가 바뀌었다"

    outputs = []
    for name, order, fname in (
        ("본편", MAIN, "토큰_절약_발표_본편.pptx"),
        ("보너스", BONUS, "토큰_절약_발표_보너스.pptx"),
    ):
        kit.new_deck()
        run(chunks, order, kit)
        path = kit.save(os.path.join(PRES, fname))
        outputs.append((name, len(order), path))

    print("-" * 60)
    for name, n, path in outputs:
        print(f"{name}: {n}장 → {os.path.basename(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
