#!/usr/bin/env python3
"""Rendered/behavioral acceptance checks. Requires playwright + Chromium.

Missing browser dependencies are NOT a pass. These tests cover explicit ACs,
not design preference, historical intermediate artifacts or general quality.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def browser_checks(kind, path):
    from playwright.sync_api import sync_playwright
    results = []

    def add(name, ok, detail=""):
        results.append({"name": name, "ok": bool(ok), "detail": str(detail)})

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.set_default_timeout(2000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # Files must be self-contained. External requests cannot make a test pass.
        page.route("https://**/*", lambda route: route.abort())
        page.route("http://**/*", lambda route: route.abort())
        page.goto(Path(path).resolve().as_uri())
        try:
            if kind == "memo":
                page.evaluate("localStorage.clear()")
                page.reload()
                page.locator("#new").click()
                page.locator("#title").fill("audit memo A")
                page.locator("#body").fill("first saved body")
                page.reload()
                add("새로고침 후 제목·본문 유지", page.locator("#title").input_value() == "audit memo A"
                    and page.locator("#body").input_value() == "first saved body")
                page.locator("#new").click()
                page.locator("#title").fill("audit memo B")
                page.locator("#body").fill("second body")
                page.locator("#list .item").filter(has_text="audit memo A").click()
                add("두 메모 중 목록 클릭 시 해당 내용 로드", page.locator("#body").input_value() == "first saved body")
                page.locator("#del").click()
                page.reload()
                add("삭제 후 새로고침에서도 삭제 유지", page.locator("#list .item").count() == 1
                    and page.locator("#title").input_value() == "audit memo B")
            elif kind == "cafe":
                details = page.locator(".menu-grid .card").evaluate_all("cards => cards.map(c => ({name:!!c.querySelector('h3')?.textContent.trim(), description:!!c.querySelector('p')?.textContent.trim(), price: /[0-9,]+/.test(c.querySelector('.price')?.textContent || ''), tag:!!c.querySelector('.tag')?.textContent.trim()}))")
                add("렌더링 메뉴 6개 각각 이름·설명·가격·태그", len(details) == 6 and all(all(x.values()) for x in details), details)
                for width in (390, 820, 821, 1280):
                    page.set_viewport_size({"width": width, "height": 900})
                    for selector in (".menu-grid", ".loc-in", ".strip", ".hero"):
                        tracks = page.locator(selector).evaluate("el => getComputedStyle(el).gridTemplateColumns.trim().split(/\\s+/).length")
                        add(f"{width}px {selector} 그리드", tracks == 1 if width <= 820 else tracks >= 2, f"columns={tracks}")
                    display = page.locator(".anchors").evaluate("el => getComputedStyle(el).display")
                    add(f"{width}px 데스크톱 메뉴 표시 조건", (display == "none") == (width <= 820), display)
                    size = page.evaluate("({scroll:document.documentElement.scrollWidth, client:document.documentElement.clientWidth})")
                    add(f"{width}px 가로 스크롤 없음", size["scroll"] <= size["client"], size)
                page.set_viewport_size({"width": 1280, "height": 900})
                for target in ("menu", "location", "hours"):
                    page.evaluate("window.scrollTo({top:0, behavior:'instant'})")
                    page.locator(f'.anchors a[href="#{target}"]').click()
                    page.wait_for_function("window.scrollY > 50")
                    add(f"앵커 #{target} 실제 이동", page.evaluate("location.hash") == f"#{target}" and page.evaluate("window.scrollY") > 50)
            else:
                raise ValueError(kind)
        except Exception as e:
            add("동작 시퀀스 완료", False, f"{type(e).__name__}: {str(e)[:180]}")
        add("브라우저 JavaScript 오류 0건", not errors, errors)
        browser.close()
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kind", choices=["memo", "cafe"])
    ap.add_argument("--file", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    path = args.file or (ROOT / ("demo/memo.html" if args.kind == "memo" else "demo/vibe_vs_spec/artifacts/index_spec.html"))
    try:
        checks = browser_checks(args.kind, path)
    except Exception as e:
        print(f"UNVERIFIED: browser unavailable / setup failed ({type(e).__name__})", file=sys.stderr)
        return 2
    for c in checks:
        print(f"{'PASS' if c['ok'] else 'FAIL'} {c['name']} {c['detail']}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"evidence_type": "browser_behavior_test", "kind": args.kind,
                                        "checks": checks}, ensure_ascii=False, indent=2) + "\n")
    print(f"{sum(c['ok'] for c in checks)}/{len(checks)}; rendered AC coverage only")
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
