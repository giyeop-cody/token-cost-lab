# -*- coding: utf-8 -*-
"""저장 발화 재생 — 저장된 세션 기록을 분류기·사다리에 그대로 태운다.
입력은 전부 저장소에 있는 실제 발화. 발화는 저장본, 정책 비용·성과는 가정."""
print("[증거 범위] 저장 발화/산출물의 재생 + 정책 비용 시나리오. 실제 정책 A/B의 품질·성공률·절감 실측 아님.")

import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent_setup"))
from intent_guard import classify_mismatch, MISMATCH_KINDS, ACLedger
from ladder_b import IntentTracker
from router import Tier

def user_turns(md):
    t = (ROOT / md).read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r'\*\*USER\*\*\s*\n+```\n(.*?)\n```', t, re.S):
        s = re.sub(r'\n*---+\s*요청 컨텍스트.*', '', m.group(1), flags=re.S)
        out.append(s.strip())
    return out

A = user_turns("demo/transcripts/persona_A_wasteful.md")
B = user_turns("demo/transcripts/persona_B_frugal.md")

print("="*84); print("1. 페르소나 A 저장 발화 6턴 — 반려 발화 분류 (턴1은 최초 지시)"); print("="*84)
ledger = ACLedger(); hit = 0; rej = 0
for i, u in enumerate(A, 1):
    if i == 1:
        print(f"\n턴{i} [최초지시] {u}"); continue
    rej += 1
    kind, ev = classify_mismatch(u)
    ok = kind != "unknown"; hit += ok
    info = MISMATCH_KINDS.get(kind)
    print(f"\n턴{i} {u}")
    if info:
        print(f"   판정 {info['label']}({kind})  근거={ev}  →칸={info['rung']}  "
              f"{'티어↑' if info['tier_up'] else '티어유지'}")
    else:
        print(f"   판정 unknown — {ev}")
    rec = ledger.promote(u, task_id=f"A{i}")
    print(f"   AC승격 {'○' if rec else '×'}")
print(f"\n>>> 저장 발화 비-unknown 분류 비율 (정답 라벨 정확도 아님): {hit}/{rej} = {hit/rej*100:.0f}%  (나머지는 unknown=되물어야 함)")
print("승격 AC:"); print(ledger.as_checklist())

print("\n" + "="*84); print("2. 같은 6턴을 사다리 B 감지기에 통과"); print("="*84)
tr = IntentTracker()
esc = 0
for i, u in enumerate(A, 1):
    d = tr.observe(u)
    if d["action"] in ("escalate", "respec"): esc += 1
    print(f"턴{i}  action={d['action']:<11} step={d['step']:<11} tier={d['tier'].name:<6} "
          f"scope={d['scope']:<7} sim={d['similarity']:.2f}")
print(f"\n>>> B 사다리 에스컬레이션: {esc}/{len(A)-1}회. "
      f"최종 칸={tr.rung}, 티어={tr._tier.name}")

print("\n" + "="*84); print("3. 페르소나 B 저장 발화 2턴"); print("="*84)
tr2 = IntentTracker()
for i, u in enumerate(B, 1):
    d = tr2.observe(u)
    k = "(최초지시)" if i == 1 else classify_mismatch(u)[0]
    print(f"턴{i} action={d['action']:<11} 분류={k:<10} | {u[:46].replace(chr(10),' / ')}")
