# -*- coding: utf-8 -*-
"""케이스 검증 — AC는 통과했는데 의도와 어긋난 항목이 실제로 있는가.
입력: demo/vibe_vs_spec 실산출물 2개(발화는 저장본, 정책 비용·성과는 가정)."""
print("[증거 범위] 저장 발화/산출물의 재생 + 정책 비용 시나리오. 실제 정책 A/B의 품질·성공률·절감 실측 아님.")

import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent_setup"))
from intent_guard import classify_mismatch, MISMATCH_KINDS

V = (ROOT/"demo/vibe_vs_spec/artifacts/index_vibe.html").read_text(encoding="utf-8")
S = (ROOT/"demo/vibe_vs_spec/artifacts/index_spec.html").read_text(encoding="utf-8")

def visible(h):
    h = re.sub(r'<style[\s\S]*?</style>', '', h)
    h = re.sub(r'<svg[\s\S]*?</svg>', ' ', h)
    return [x.strip() for x in re.split(r'<[^>]+>', h) if x.strip()]

def norm(s):  # HTML 엔티티 차이는 표기 차이일 뿐
    return s.replace("&amp;", "&").replace("&nbsp;", " ").strip()

tv = [norm(x) for x in visible(V)]
ts = set(norm(x) for x in visible(S))
lost = [x for x in tv if x not in ts]

print("="*78)
print("케이스: 카페 온도 랜딩 (req_1786763476385 → req_1786764007807)")
sys.path.insert(0, str(ROOT))
from demo.vibe_vs_spec.verify_ac import run as verify_ac
if verify_ac(ROOT / "demo/vibe_vs_spec/artifacts/index_spec.html") != 0:
    raise SystemExit("현재 AC 검증 실패 — PASS로 소개하지 않음")
print("현재 정적/브라우저 AC를 실행했다. 아래는 검증 범위 밖의 가상 반려다.")
print("="*78)
print(f"\n그런데 사용자가 보는 화면에서 사라진 문구: {len(lost)}건\n")
for x in lost:
    print(f"   ✗ {x}")

print("\n" + "-"*78)
print("이 항목들을 잡는 AC가 16개 중에 있는가 — 전수 대조")
print("-"*78)
ac_src = (ROOT/"demo/vibe_vs_spec/verify_ac.py").read_text(encoding="utf-8")
ac_names = re.findall(r'add\("([^"]+)"', ac_src)
for x in lost:
    key = re.split(r'[\s(·—]', x)[0][:6]
    covered = [n for n in ac_names if key and key in ac_src.split(n)[0][-200:]]
    print(f"  {x[:42]:<44} → 커버하는 AC: {'없음' if not covered else covered}")

print("\n" + "="*78)
print("사용자가 이걸 발견하고 반려한다면 — 분류기 판정")
print("="*78)
fb = "영업시간에서 라스트오더 표기가 빠졌다. 원래 있던 건데 왜 없어졌나"
kind, ev = classify_mismatch(fb)
info = MISMATCH_KINDS[kind]
print(f'반려 발화: "{fb}"')
print(f"  → {info['label']}({kind})  근거={ev}")
print(f"  → 대응칸={info['rung']}  티어상승={'필요' if info['tier_up'] else '불필요'}")
print(f"  → 처방: {info['fix']}")
