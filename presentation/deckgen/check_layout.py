#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_layout.py — 슬라이드 텍스트가 카드/도형 밖으로 넘치는지 자동 검출한다.

python-pptx는 렌더링을 하지 않으므로 "글자가 넘쳤다"를 알 수 없다.
그래서 PIL로 실제 폰트 메트릭을 재서, 각 텍스트 상자가 차지할 높이를 계산하고
그것을 담고 있는 카드(rect)의 경계와 비교한다.

    python check_layout.py            # 넘친 것만
    python check_layout.py -v         # 전부
"""
import argparse
import glob
import os
import sys

from pptx import Presentation
from pptx.util import Emu
from PIL import ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))   # presentation/build/
PRES = os.path.dirname(HERE)                        # presentation/
EMU_IN = 914400.0
SLIDE_W, SLIDE_H = 13.333, 7.5


def find_font():
    pats = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/**/NanumGothic*.ttf",
        "/usr/share/fonts/**/*CJK*KR*.otf",
        "/usr/share/fonts/**/DejaVuSans.ttf",
    ]
    for p in pats:
        hits = sorted(glob.glob(p, recursive=True))
        if hits:
            return hits[0]
    return None


FONT_PATH = find_font()
_cache = {}


def font(px):
    px = max(int(round(px)), 6)
    if px not in _cache:
        _cache[px] = (ImageFont.truetype(FONT_PATH, px) if FONT_PATH
                      else ImageFont.load_default())
    return _cache[px]


def text_w(s, pt):
    """pt 크기 글자의 폭을 인치로."""
    if not s:
        return 0.0
    px = pt * 4          # 4px per pt → 측정 후 /4 해서 pt, /72 해서 inch
    f = font(px)
    try:
        w = f.getlength(s)
    except AttributeError:
        w = f.getsize(s)[0]
    return w / 4.0 / 72.0


def para_lines(text, pt, box_w_in):
    """상자 폭에서 몇 줄로 감기는지."""
    if not text.strip():
        return 1
    if box_w_in <= 0:
        return 1
    lines, cur = 1, ""
    for ch in text:
        t = cur + ch
        if text_w(t, pt) > box_w_in and cur:
            lines += 1
            cur = ch
        else:
            cur = t
    return lines


def frame_height(shape):
    """텍스트 프레임이 실제로 차지하는 높이(인치)."""
    tf = shape.text_frame
    w = Emu(shape.width).inches
    # 내부 여백
    li = (tf.margin_left or 0) / EMU_IN
    ri = (tf.margin_right or 0) / EMU_IN
    ti = (tf.margin_top or 0) / EMU_IN
    bi = (tf.margin_bottom or 0) / EMU_IN
    avail = w - li - ri
    total = ti + bi
    for p in tf.paragraphs:
        sizes = [r.font.size.pt for r in p.runs if r.font.size]
        pt = max(sizes) if sizes else 18.0
        txt = "".join(r.text for r in p.runs)
        n = para_lines(txt, pt, avail)
        ls = 1.15
        if p.line_spacing:
            try:
                ls = float(p.line_spacing)
            except (TypeError, ValueError):
                ls = 1.15
        before = (p.space_before.pt / 72.0) if p.space_before else 0.0
        after = (p.space_after.pt / 72.0) if p.space_after else 0.0
        total += before + after + n * (pt * ls / 72.0)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pptx", default=os.path.join(PRES, "토큰_절약_발표.pptx"))
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    if not FONT_PATH:
        print("⚠️ 한글 폰트를 못 찾음 — 폭 계산이 부정확할 수 있음")

    prs = Presentation(a.pptx)
    issues = []

    for i, s in enumerate(prs.slides, 1):
        # 카드/판때기 후보: 텍스트 없는 큰 사각형
        cards = []
        for sh in s.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                continue
            try:
                w, h = Emu(sh.width).inches, Emu(sh.height).inches
            except TypeError:
                continue
            if w > 1.2 and h > 0.5:
                cards.append((Emu(sh.left).inches, Emu(sh.top).inches, w, h))

        for sh in s.shapes:
            if not sh.has_text_frame or not sh.text_frame.text.strip():
                continue
            x, y = Emu(sh.left).inches, Emu(sh.top).inches
            w, h = Emu(sh.width).inches, Emu(sh.height).inches
            head0 = sh.text_frame.text.strip().split("\n")[0][:44]
            # 음수/0 높이 = 카드보다 본문이 길어 계산이 뒤집힌 것. 명백한 버그다.
            if h <= 0 or w <= 0:
                issues.append((i, "상자 크기 이상", head0, h, 0.0))
                continue
            need = frame_height(sh)
            bottom = y + need
            head = sh.text_frame.text.strip().split("\n")[0][:44]

            # 1) 슬라이드 밖으로
            if bottom > SLIDE_H - 0.04:
                issues.append((i, "슬라이드 이탈", head, bottom, SLIDE_H))
                continue

            # 2) 자기를 담은 카드 밖으로
            # 카드 '안'에 있다고 보려면 텍스트 시작점이 카드 상단보다 아래이고
            # 카드 세로 범위 안에서 시작해야 한다. 카드 아래에 의도적으로 배치한
            # 문단(예: 슬라이드 18 실무 규칙)을 오탐하지 않기 위함.
            host = None
            for cx, cy, cw, ch in cards:
                inside_x = x >= cx - 0.12 and x + w <= cx + cw + 0.12
                starts_in_y = cy - 0.02 <= y <= cy + ch - 0.10
                if inside_x and starts_in_y:
                    if host is None or (cy + ch) < host:
                        host = cy + ch
            if host and bottom > host + 0.05:
                issues.append((i, "카드 이탈", head, bottom, host))

    if issues:
        print(f"레이아웃 문제 {len(issues)}건\n" + "─" * 74)
        for sl, kind, head, got, lim in issues:
            print(f"  슬라이드 {sl:>2}  [{kind}]  {head}")
            print(f"      텍스트 하단 {got:.2f}in > 한계 {lim:.2f}in "
                  f"(초과 {got-lim:.2f}in)")
    else:
        print("✓ 레이아웃 이탈 없음")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
