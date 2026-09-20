# -*- coding: utf-8 -*-
"""Spec 산출물 AC 검증 — 정적 16항목 + 실제 Chromium 레이아웃/동작.

케이스 스터디(demo/vibe_vs_spec)의 Spec 모드 산출물이
4필드 스펙(pages·stack·design·ac)을 결정적으로 준수하는지 검사한다.

실행:
  python demo/vibe_vs_spec/verify_ac.py
  python demo/vibe_vs_spec/verify_ac.py --file path/to/other.html
"""
import argparse
import re
import sys
from pathlib import Path

DEFAULT = Path(__file__).parent / "artifacts" / "index_spec.html"


def run(path: Path, static_only=False) -> int:
    html = path.read_text(encoding="utf-8")
    checks = []
    add = lambda name, ok, note="": checks.append((name, ok, note))

    cards = len(re.findall(r'<article class="card">', html))
    add("AC1 메뉴 카드 정확히 6개", cards == 6, f"cards={cards}")
    tags = len(re.findall(r'class="tag', html))
    add("AC1 카드마다 태그 존재(6개)", tags == 6, f"tags={tags}")
    loc = sum(1 for k in ["주소", "지하철", "버스", "주차", "문의"] if f"<b>{k}</b>" in html)
    add("AC2 오시는길 5개 항목", loc == 5, f"items={loc}")
    add("AC3 820px 미디어쿼리", "@media (max-width:820px)" in html)
    add("AC3 데스크톱 메뉴 숨김", bool(re.search(r"820px[\s\S]*?\.anchors\{display:none\}", html)))
    add("AC3 overflow-x 차단", "overflow-x:hidden" in html)
    anchors = all(f'href="{a}"' in html and f'id="{a[1:]}"' in html for a in ["#menu", "#location", "#hours"])
    add("AC4 앵커 3종 href+id 매칭", anchors)
    add("AC4 smooth scroll", "scroll-behavior:smooth" in html)
    add("AC5 영업시간 명시", "09:00 – 21:00" in html and "10:00 – 22:00" in html and "첫째 주 월요일" in html)
    add("STACK JS 금지", "<script" not in html)
    add("STACK 외부 리소스 금지", not re.search(r"https?://", html) and "<link" not in html and "<img" not in html)
    add("STACK 시맨틱 태그", all(t in html for t in ["<nav>", "<header>", "<section", "<footer>"]))
    palette = ["#faf6f0", "#e8dccb", "#c08552", "#3e2f25", "#6f4e37", "#7a8450"]
    add("DESIGN 팔레트 6색", all(c in html for c in palette))
    add("DESIGN radius/패딩 토큰", all(v in html for v in ["--r-card:20px", "--r-btn:12px", "--sec-pad:84px"]))
    add("DESIGN h1 clamp(34~52)", "clamp(34px,5vw,52px)" in html)
    add("DESIGN 호버 translateY(-6px)", "translateY(-6px)" in html)

    passed = 0
    for name, ok, note in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({note})" if note else ""))
        passed += ok
    print(f"\n정적 문자열/구조 검사 {passed}/{len(checks)} (동작 보증 아님)")
    if static_only:
        print("STATIC ONLY — 실제 AC gate 미검증")
        return 0 if passed == len(checks) else 1
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.browser_ac import browser_checks
    try:
        dynamic = browser_checks("cafe", path)
    except Exception as e:
        print(f"UNVERIFIED browser: {type(e).__name__}; install requirements-dev + playwright chromium")
        return 2
    for c in dynamic:
        print(f"{'PASS' if c['ok'] else 'FAIL'}  {c['name']} {c['detail']}")
    return 0 if passed == len(checks) and all(c["ok"] for c in dynamic) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=DEFAULT)
    ap.add_argument("--static-only", action="store_true", help="partial inspection only, not an AC gate")
    args = ap.parse_args()
    sys.exit(run(args.file, args.static_only))
