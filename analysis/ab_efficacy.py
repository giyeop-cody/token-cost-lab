# -*- coding: utf-8 -*-
"""A/B 사다리 각각의 효용을 실로그로 측정.

핵심 질문: 페르소나 A의 반려 5턴 중
  - A 사다리(트리거=AC 실패)가 막았을 턴은 몇 개인가
  - B 사다리(트리거=사용자 반복)가 막았을 턴은 몇 개인가
관할이 다르므로 따로 센다.
"""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent_setup"))

# ── 페르소나 B의 스펙에 실제로 적힌 완료조건 (persona_B_frugal.md 원문) ──
# "[완료조건] 새로고침 후 데이터 유지 / 목록 클릭 시 정상 로드 / 콘솔 에러 0"
# 이걸 결정론적 AC로 옮긴다. A 사다리는 이런 AC 실패로만 돈다.
MEMO = (ROOT / "demo/memo.html").read_text(encoding="utf-8")

def ac_persist(html):     # 완료조건1: 새로고침 후 데이터 유지
    return "localStorage.setItem" in html and "localStorage.getItem" in html
def ac_click(html):       # 완료조건2: 목록 클릭 시 정상 로드
    return bool(re.search(r"onclick|addEventListener\(\s*['\"]click", html))
def ac_single(html):      # 사용자 턴2 요구: 단일 HTML 파일
    return "<script" in html and "<style" in html and "import " not in html

ACS = [("새로고침 후 데이터 유지", ac_persist),
       ("목록 클릭 시 정상 로드", ac_click),
       ("단일 HTML 파일", ac_single)]

print("="*80)
print("0. 완료조건을 AC로 옮기면 결정론적으로 검사되는가 — 최종 산출물로 확인")
print("="*80)
for name, fn in ACS:
    print(f"   {'PASS' if fn(MEMO) else 'FAIL'}  {name}")

# ── 실로그 5개 반려 턴을 '관할'로 라벨링 ──
# 근거는 페르소나 A 로그의 ASSISTANT 자백 문장.
TURNS = [
  dict(n=2, utt="아니 이렇게 복잡한 거 말고... 그냥 html 파일 하나로 되는 거",
       cause="스펙 미합의(사용자가 원한 형태를 안 말했음)",
       ac_catchable=False,
       note="AC 없음 — 사용자가 결과를 봐야 알 수 있다. B 관할."),
  dict(n=3, utt="디자인이 너무 밋밋한데 다크 테마로 해줘",
       cause="취향", ac_catchable=False,
       note="AC로 못 만든다(취향). B 관할이지만 B도 못 고침."),
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
       note="앞 턴들이 막혔으면 발생 자체를 안 함. 파생 턴."),
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
print(f"A 사다리가 잡는 턴: {len(a_catch)}/5  ({[t['n'] for t in a_catch]})")
print(f"B 사다리 관할 턴  : {5-len(a_catch)}/5")
