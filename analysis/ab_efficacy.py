# -*- coding: utf-8 -*-
"""최종 산출물 AC 검사와 과거 전사에 대한 사후 관할 분류.

핵심 질문: 페르소나 A의 반려 5턴 중
  - A 사다리(트리거=AC 실패)가 검출 가능하다고 가정하는 턴은 몇 개인가
  - B 사다리(트리거=사용자 반복)가 검출 가능하다고 가정하는 턴은 몇 개인가
관할이 다르므로 따로 센다.
"""
print("[증거 범위] 저장 발화/산출물의 재생 + 정책 비용 시나리오. 실제 정책 A/B의 품질·성공률·절감 실측 아님.")

import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent_setup"))

# ── 페르소나 B의 스펙에 실제로 적힌 완료조건 (persona_B_frugal.md 원문) ──
# "[완료조건] 새로고침 후 데이터 유지 / 목록 클릭 시 정상 로드 / 콘솔 에러 0"
# 이걸 결정론적 AC로 옮긴다. A 사다리는 이런 AC 실패로만 돈다.
sys.path.insert(0, str(ROOT))
from tools.browser_ac import browser_checks

print("최종 메모 산출물의 브라우저 동작 검사 (이전 중간 산출물 재현 아님)")
checks = browser_checks("memo", ROOT / "demo/memo.html")
for c in checks:
    print(f"{'PASS' if c['ok'] else 'FAIL'} {c['name']}")
if not all(c["ok"] for c in checks):
    raise SystemExit(1)
print("아래 관할 분류는 전사 설명에 근거한 사후 가정. A가 실제 해당 턴을 예방했다고 관측하지 않음.")

# ── 저장 발화 5개 반려 턴을 '관할'로 라벨링 ──
# 근거는 페르소나 A 로그의 ASSISTANT 자백 문장.
TURNS = [
  dict(n=2, utt="아니 이렇게 복잡한 거 말고... 그냥 html 파일 하나로 되는 거",
       cause="스펙 미합의(사용자가 원한 형태를 안 말했음)",
       ac_catchable=False,
       note="AC 없음 — 사용자가 결과를 봐야 알 수 있다. B 관할."),
  dict(n=3, utt="디자인이 너무 밋밋한데 다크 테마로 해줘",
       cause="취향", ac_catchable=False,
       note="당시 명시 AC에 없는 취향. 별도 합의·평가가 필요한 것으로 분류."),
  dict(n=4, utt="저장이 안 되는 것 같은데? 새로고침하면 사라져",
       cause="이벤트 핸들러에서 save() 미호출 (로그의 어시스턴트 자백)",
       ac_catchable=True, ac="새로고침 후 데이터 유지",
       note="결정론 AC로 잡힌다. A 관할."),
  dict(n=5, utt="이제 저장은 되는데 목록에서 클릭해도 안 열려",
       cause="렌더 후 리스너 재등록 누락 (로그의 어시스턴트 자백)",
       ac_catchable=True, ac="목록 클릭 시 정상 로드",
       note="결정론 AC로 잡힌다. A 관할."),
  dict(n=6, utt="처음부터 심플하게 다시 만들어줘. 이벤트버스 이런 거 다 빼고",
       cause="턴2~5 누적 결과 전면 재작성", ac_catchable=False,
       note="앞 턴을 막으면 소멸한다고 가정; 실제 예방 효과는 미측정."),
]

print("\n" + "="*80)
print("1. 반려 5턴의 관할 분해 — 누가 막을 수 있었나")
print("="*80)
a_catch = [t for t in TURNS if t["ac_catchable"]]
for t in TURNS:
    owner = "A(AC실패)" if t["ac_catchable"] else "B/기타"
    print(f"\n턴{t['n']} {t['utt'][:46]}")
    print(f"   원인: {t['cause']}")
    print(f"   관할: {owner:<10} {t['note']}")

print("\n" + "-"*80)
print(f"A 사다리로 검출 가능하다고 가정한 턴: {len(a_catch)}/5  ({[t['n'] for t in a_catch]})")
print(f"B 사다리 관할 턴  : {5-len(a_catch)}/5")
