#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_pdf.py — 토큰_절약_발표.pptx 를 PDF로 변환한다 (전자칠판 백업용).

덱은 '맑은 고딕' 기준으로 만들어졌다. 이 폰트는 Windows 전용이라
Linux/macOS에서 변환하면 LibreOffice가 임의의 폰트로 치환하고,
그 결과 **글자가 넓어져 표 밖으로 넘치거나 줄이 깨진다.**
그래서 변환 전에 fontconfig 별칭으로 한글 대체 폰트를 명시적으로 지정한다.

  python make_pdf.py                    # 옆의 pptx → pdf
  python make_pdf.py --check            # 변환 후 쪽수·텍스트 추출 검증까지
  python make_pdf.py --in a.pptx --out b.pdf

요구: LibreOffice(soffice). 없으면 설치 명령을 안내하고 종료한다.
  Debian/Ubuntu : sudo apt-get install -y libreoffice-impress fonts-nanum
  macOS         : brew install --cask libreoffice
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))   # presentation/build/
PRES = os.path.dirname(HERE)                        # presentation/ (산출물)
DEFAULT_IN = os.path.join(PRES, "토큰_절약_발표.pptx")
DEFAULT_OUT = os.path.join(PRES, "토큰_절약_발표.pdf")

# 덱이 쓰는 폰트 → 없을 때 쓸 대체 폰트(우선순위)
SUBSTITUTES = {
    "맑은 고딕": ["Malgun Gothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR"],
    "Malgun Gothic": ["NanumGothic", "Noto Sans CJK KR", "Noto Sans KR"],
    "Consolas": ["NanumGothicCoding", "DejaVu Sans Mono", "Liberation Mono"],
}

# 시스템 fonts.conf를 먼저 include 해야 한다.
# include 없이 규칙만 쓰면 LibreOffice가 폰트를 하나도 못 찾는다
# ("No fonts could be found on the system.")
FONTCONFIG = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
{rules}
</fontconfig>
"""

RULE = """  <match target="pattern">
    <test qual="any" name="family"><string>{src}</string></test>
    <edit name="family" mode="assign" binding="strong">
{prefs}    </edit>
  </match>
"""


def have_soffice():
    for c in ("soffice", "libreoffice"):
        p = shutil.which(c)
        if p:
            return p
    return None


def installed_families():
    """fc-list로 설치된 폰트 패밀리 집합을 얻는다."""
    try:
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True,
                             text=True, timeout=30).stdout
    except Exception:
        return set()
    fams = set()
    for line in out.splitlines():
        for f in line.split(","):
            fams.add(f.strip())
    return fams


def write_fontconfig(path):
    """설치된 폰트 중 첫 번째 후보로 치환 규칙을 만든다."""
    fams = installed_families()
    rules, chosen = [], {}
    for src, cands in SUBSTITUTES.items():
        picks = [c for c in cands if c in fams]
        if not picks:
            continue
        chosen[src] = picks[0]
        prefs = "".join(f"      <string>{c}</string>\n" for c in picks)
        rules.append(RULE.format(src=src, prefs=prefs))
    with open(path, "w", encoding="utf-8") as f:
        f.write(FONTCONFIG.format(rules="".join(rules)))
    return chosen


def convert(src, dst, timeout=300):
    soffice = have_soffice()
    if not soffice:
        sys.exit(
            "soffice(LibreOffice)를 찾을 수 없습니다.\n"
            "  Debian/Ubuntu : sudo apt-get install -y libreoffice-impress fonts-nanum\n"
            "  macOS         : brew install --cask libreoffice"
        )
    if not os.path.exists(src):
        sys.exit(f"입력 파일이 없습니다: {src}")

    workdir = tempfile.mkdtemp(prefix="pptx2pdf_")
    profile = os.path.join(workdir, "profile")
    fcfile = os.path.join(workdir, "fonts.conf")
    chosen = write_fontconfig(fcfile)

    if chosen:
        print("  폰트 치환:")
        for k, v in chosen.items():
            mark = "(그대로)" if k == v else "→"
            print(f"    {k:14} {mark} {v}")
    else:
        print("  ⚠️ 대체 폰트를 찾지 못했습니다. 한글이 깨질 수 있습니다.")
        print("     sudo apt-get install -y fonts-nanum  (또는 fonts-noto-cjk)")

    env = dict(os.environ)
    env["FONTCONFIG_FILE"] = fcfile
    env["HOME"] = workdir            # 사용자 프로파일 오염 방지
    env["SAL_USE_VCLPLUGIN"] = "svp"  # 헤드리스 렌더링

    cmd = [soffice, "--headless", "--norestore", "--nolockcheck",
           f"-env:UserInstallation=file://{profile}",
           "--convert-to", "pdf:impress_pdf_Export",
           "--outdir", workdir, src]
    print(f"  변환 중… ({os.path.basename(src)})")
    r = subprocess.run(cmd, capture_output=True, text=True,
                       timeout=timeout, env=env)
    produced = os.path.join(workdir, os.path.splitext(os.path.basename(src))[0] + ".pdf")
    if not os.path.exists(produced):
        print(r.stdout, r.stderr, file=sys.stderr)
        sys.exit("변환 실패: PDF가 생성되지 않았습니다.")
    shutil.move(produced, dst)
    shutil.rmtree(workdir, ignore_errors=True)
    return dst


def page_count(pdf):
    data = open(pdf, "rb").read()
    m = re.search(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", data, re.S)
    if m:
        return int(m.group(1))
    return len(re.findall(rb"/Type\s*/Page[^s]", data))


def slide_count(pptx):
    try:
        from pptx import Presentation
        return len(Presentation(pptx).slides._sldIdLst)
    except Exception:
        return None


def check(pptx, pdf):
    ok = True
    pages, slides = page_count(pdf), slide_count(pptx)
    size = os.path.getsize(pdf)
    print("\n  검증")
    print(f"    파일 크기      {size/1024:,.0f} KB")
    print(f"    PDF 쪽수       {pages}")
    if slides is not None:
        good = pages == slides
        ok &= good
        print(f"    PPTX 장수      {slides}  {'✓ 일치' if good else '✗ 불일치'}")

    # 텍스트가 실제로 들어갔는지 (이미지로만 굽히면 검색·복사가 안 된다)
    try:
        txt = subprocess.run(["pdftotext", pdf, "-"], capture_output=True,
                             text=True, timeout=60).stdout
    except Exception:
        txt = ""
    if txt:
        has_ko = bool(re.search(r"[가-힣]", txt))
        print(f"    한글 텍스트    {'✓ 추출됨' if has_ko else '✗ 안 됨(이미지화 의심)'}")
        ok &= has_ko
        for probe in ("정답 6/6", "에러 분석 문장", "캐시 미사용 (기준)"):
            hit = probe.replace(" ", "") in txt.replace(" ", "").replace("\n", "")
            print(f"    수정 반영      {'✓' if hit else '✗'} '{probe}'")
            ok &= hit
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=DEFAULT_IN)
    ap.add_argument("--out", dest="dst", default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true", help="변환 후 검증까지 수행")
    a = ap.parse_args()

    print("=" * 70)
    print("  PPTX → PDF 변환 (전자칠판 백업용)")
    print("=" * 70)
    out = convert(a.src, a.dst)
    print(f"  저장: {out}")
    ok = True
    if a.check:
        ok = check(a.src, out)
    print("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
