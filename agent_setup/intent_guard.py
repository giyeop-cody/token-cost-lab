# -*- coding: utf-8 -*-
"""의도 불일치 — 분류 · 방지 · 확장.

'의도 불일치'란 무엇인가:

    AC는 전부 통과했는데 사용자가 "이거 아닌데"라고 하는 상태.

이건 모델이 멍청해서 생기는 게 아니다. **AC가 의도의 부분집합**이라서
생긴다. 커피숍 랜딩 케이스의 기존 AC 16개는 구조적 검사였고, 현재 브라우저 동작 검사를 추가했다 —
'카드 6개', '미디어쿼리 820px', '팔레트 6색'. 어느 것도
"이게 정말 원하던 랜딩페이지인가"를 묻지 않는다.

    의도 ⊃ 명시된 AC        ← 이 차집합이 의도 불일치의 서식지
    검증기는 명시 AC 범위만 본다 ← 범위 밖의 의도는 추가 평가가 필요하다

따라서 대책은 세 방향이다:
  방지  — 구현 **전에** 차집합을 줄인다 (선반영/사전확인)
  고도화 — 반려 사유를 분류해 **맞는 칸으로** 보낸다 (맹목적 등반 금지)
  확장  — 반려를 **영구 AC로 승격**해 같은 불일치가 재발하지 않게 한다
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── 1. 의도 불일치 분류 ──────────────────────────────────────
# 종류마다 '올바른 대응'이 다르다. 전부 티어를 올리는 건 낭비다.
MISMATCH_KINDS = {
    "scope": {
        "label": "범위 어긋남",
        "desc": "시킨 것보다 많이/적게 했다",
        "fix": "범위 재합의 — 티어를 올려도 안 고쳐진다",
        "rung": "widen",       # 범위 축을 움직인다
        "tier_up": False,
    },
    "taste": {
        "label": "취향·표현",
        "desc": "맞는데 마음에 안 든다 (색·톤·문체)",
        "fix": "예시 2~3개 제시 후 택일 — 추론 난이도 문제가 아니다",
        "rung": "same",        # 같은 칸에서 변주만
        "tier_up": False,
    },
    "assumption": {
        "label": "숨은 전제",
        "desc": "말 안 한 제약을 어겼다 (기존 컨벤션·의존성)",
        "fix": "전제를 AC로 승격 — 다음부터 자동 검사",
        "rung": "widen",
        "tier_up": False,
    },
    "reasoning": {
        "label": "판단 오류",
        "desc": "설계 판단이 틀렸다 (알고리즘·구조)",
        "fix": "티어 상승 — 여기가 모델 능력 문제인 유일한 칸",
        "rung": "tier-up",
        "tier_up": True,
    },
    "stale": {
        "label": "맥락 오염",
        "desc": "앞 대화의 폐기된 결정을 아직 붙들고 있다",
        "fix": "세션 리셋 — 모델을 바꿔도 같은 실수를 반복한다",
        "rung": "reset",
        "tier_up": False,
    },
}

_PATTERNS = [
    ("stale", r"(아직도|여전히|계속|또\s*그|바꿨는데|말했는데|아까\s*말한|이미\s*말)"),
    ("scope", r"(\S+만\s*(건드|하|고치|수정|바꿔)|그것?만|까지만|빼고|말고도|너무\s*(많|과)|많이\s*(바꾸|바꿨|고쳤|건드)|과하|범위|전부\s*다|건드리지|손대지)"),
    ("taste", r"(색|톤|느낌|디자인|예쁘|촌스|스타일|문체|말투|어색)"),
    ("assumption", r"(원래|기존|컨벤션|규칙|우리\s*(는|팀)|늘|항상|쓰던)"),
    ("reasoning", r"(틀렸|잘못|버그|안\s*돌아|성능|느리|구조|설계|방식이)"),
]


def classify_mismatch(feedback: str) -> tuple[str, str]:
    """사용자 반려 문장 → 불일치 종류.

    반환: (kind, 근거). 못 고르면 ("unknown", 사유).

    분류가 중요한 이유: 종류마다 대응이 다르다. '취향' 불일치에
    LARGE 모델을 붙이는 건 돈만 쓰고 안 고쳐진다 — 추론 난이도
    문제가 아니기 때문이다.
    """
    text = feedback.strip()
    hits = [(k, m.group(0)) for k, p in _PATTERNS
            if (m := re.search(p, text))]
    if not hits:
        return "unknown", "분류 신호 없음 — 사용자에게 되물어야 한다"
    if len(hits) > 1:
        # 맥락 오염이 섞이면 그게 우선이다. 다른 걸 먼저 고쳐도
        # 오염된 맥락이 남아 있으면 되돌아온다.
        for k, ev in hits:
            if k == "stale":
                return k, f"'{ev}' — 반복 신호가 우선"
    return hits[0][0], f"'{hits[0][1]}'"


# ── 2. 방지 — 구현 전에 차집합을 줄인다 ───────────────────────
PREFLIGHT_IN_TOK = 600      # 작업 지시 + 기존 스펙
PREFLIGHT_OUT_TOK = 200     # 재진술 + 빠진 AC 후보


def preflight_prompt(task: str) -> str:
    """구현 **전에** SMALL 모델로 한 번 되짚는 프롬프트.

    핵심은 '질문을 많이 하라'가 아니다 — 그건 사용자를 지치게 한다.
    **암묵 전제를 명시화**하고, 갈림길이 있을 때만 묻게 한다.
    """
    return (
        "다음 작업을 구현하기 전에, 아래 세 줄만 출력한다.\n"
        "1) 내가 이해한 결과물 한 문장\n"
        "2) 명시되지 않았지만 내가 가정한 것 (최대 3개)\n"
        "3) 이 가정 중 틀리면 전부 다시 해야 하는 것 하나\n"
        "질문은 3)에 대해서만, 그것도 갈림길이 실제로 있을 때만 한다.\n"
        f"---\n작업: {task}"
    )


def preflight_cost(tier="small") -> float:
    from router import cost_of, Tier
    t = {"small": Tier.SMALL, "mid": Tier.MID}[tier]
    return cost_of(t, PREFLIGHT_IN_TOK, PREFLIGHT_OUT_TOK)


# ── 3. 확장 — 반려를 영구 AC로 승격 ──────────────────────────
@dataclass
class ACLedger:
    """반려 사유를 누적해 AC로 승격시키는 장부.

    이게 결합 구조에서 가장 큰 레버다. B 사다리는 한 번 돌 때마다
    비싸지만, 그때 얻은 정보를 **AC로 고정**하면 그 불일치는
    다음부터 A 사다리(싼 쪽)가 잡는다. 즉 **B에서 A로 이관**된다.

        1회차: B가 잡는다        ($0.0697/칸)
        2회차부터: A가 잡는다     (검증 $0.0003, 리워크 $0.0112)
    """
    promoted: list[dict] = field(default_factory=list)
    seen: set[str] = field(default_factory=set)

    def promote(self, feedback: str, task_id: str = "") -> dict | None:
        """반려 → AC 후보. 이미 있으면 None."""
        kind, ev = classify_mismatch(feedback)
        if kind in ("taste", "unknown"):
            # 취향은 AC로 못 만든다. 규칙화하면 다음 작업을 망친다.
            return None
        key = f"{kind}:{_normalize(feedback)}"
        if key in self.seen:
            return None
        self.seen.add(key)
        rec = {"task_id": task_id, "kind": kind, "evidence": ev,
               "source": feedback, "check": _to_check(kind, feedback)}
        self.promoted.append(rec)
        return rec

    def as_checklist(self) -> str:
        if not self.promoted:
            return "승격된 AC 없음"
        out = []
        for i, r in enumerate(self.promoted, 1):
            out.append(f"{i}. [{MISMATCH_KINDS[r['kind']]['label']}] {r['check']}")
        return "\n".join(out)


def _normalize(s: str) -> str:
    return re.sub(r"\s+", "", s)[:40]


def _to_check(kind: str, feedback: str) -> str:
    """반려 문장 → 다음 턴에 붙일 검사 문장."""
    stem = feedback.strip().rstrip(".")
    if kind == "scope":
        return f"범위 확인: {stem} — 지정 범위 밖 파일을 건드리지 않았는가"
    if kind == "assumption":
        return f"전제 확인: {stem} — 기존 컨벤션을 따랐는가"
    if kind == "reasoning":
        return f"판단 확인: {stem} — 이 설계 결정의 근거를 한 줄로 댈 수 있는가"
    if kind == "stale":
        return f"맥락 확인: {stem} — 폐기된 결정을 다시 쓰지 않았는가"
    return stem
