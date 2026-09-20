#!/usr/bin/env python3
"""전체 페이지 스크린샷 2장을 나란히 붙인 비교 이미지를 만든다.

원본(`shots/vibe_full.png`, `shots/spec_full.png`)은 손대지 않고
덱에 넣을 2-up 축소본만 새로 만든다. 세로로 긴 페이지라 덱에서는
"스크롤 길이가 비슷하다"를 보여주는 축소 자료로만 쓴다.
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SHOTS = ROOT / "shots"
GAP = 24
TARGET_H = 1600


def main():
    panels = []
    for name in ("vibe_full.png", "spec_full.png"):
        im = Image.open(SHOTS / name).convert("RGB")
        width = round(im.width * TARGET_H / im.height)
        panels.append(im.resize((width, TARGET_H), Image.LANCZOS))
    total_w = sum(p.width for p in panels) + GAP
    canvas = Image.new("RGB", (total_w, TARGET_H), (14, 20, 27))
    x = 0
    for p in panels:
        canvas.paste(p, (x, 0))
        x += p.width + GAP
    out = SHOTS / "vibe_spec_full_2up.png"
    canvas.save(out)
    print(f"{out.relative_to(ROOT.parent.parent)} {canvas.width}x{canvas.height} {out.stat().st_size:,}B")


if __name__ == "__main__":
    main()
