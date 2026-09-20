#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_personas.py — 같은 목표 결과물, 두 가지 습관의 비용 시나리오.

페르소나 A(김낭비): 토큰 절약 원칙 0개
페르소나 B(박절약): 원칙 전부 적용
→ 동일한 memo.html을 목표로 두는 모형. 두 실제 세션의 품질 동등성 실험 아님

측정 방식:
  · 일부 텍스트만 tiktoken 인코딩. 확대 출력·턴 수·사고량은 가정
  · 사고 토큰: 턴별 가정. 다른 과제/모델의 hidden reasoning에 토크나이저 배수를 적용할 근거 없음
  · 캐싱: 프리픽스 고정 여부에 따라 read/write 단가 적용
  · 에이전트 루프: 매 턴 전체 이력 재전송 (2차 함수)

    python compare_personas.py
    python compare_personas.py --model opus
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)          # token-cost-lab/ (이 파일은 그 안의 demo/)
sys.path.insert(0, LAB)

from lab import pricing  # noqa: E402

try:
    import tiktoken
except ImportError:
    sys.exit("pip install tiktoken 필요")

ENC = tiktoken.get_encoding("o200k_base")


def tok(s):
    return len(ENC.encode(s))


# ── 사고 토큰 추정 근거 ──────────────────────────────────────────
# ⚠️ 방법론 주의: LIVE_RESULTS §7의 사고/응답 비율(reason KO 5.32× / EN 7.57×)을
#    그대로 곱하면 안 된다. 그 비율은 응답 157~378토큰 규모에서 측정된 값이고,
#    실측 사고 토큰의 최대치는 3,049였다. 5,890토큰짜리 코드 덤프에 비율을 곱하면
#    사고 45,000토큰이라는, 실측 최대의 15배짜리 허구가 나온다.
#
#    사고량은 '출력 길이'가 아니라 '과제 난이도'에 붙는다.
#    코드를 길게 쓴다고 그만큼 더 생각하지 않는다. 그래서 여기서는
#    턴 성격별 사고량을 가정한다. 다른 과제의 898~3,049를 참고했지만
#    이 범위로 제한한 것은 아니며 300 같은 값과 legacy 1.44 승수가 포함된다.
THINK_OBSERVED_MAX = 3049          # §7 reason 과제 실측 최대
THINK_OBSERVED_MEAN = 1366         # §7 reason 과제 EN/KO 평균

# 턴 성격별 사고량 가정 (현재 과제의 hidden 사고 실측 아님)
THINK_DESIGN = 2600     # 새 설계·처음부터 다시 (난이도 높음)
THINK_REWORK = 1900     # 버그 원인 추적·수정 (중간)
THINK_TWEAK = 300       # 한 줄 수정 (낮음)

EFFORT_LOW = 0.35       # effort 감소 승수 가정 (벤더가 보장한 65% 절감률이 아님)
KO_PENALTY = 1.44       # legacy 승수 가정; exp01 예문 인코딩을 hidden 사고에 적용하는 것은 미검증


def read(path):
    with open(os.path.join(HERE, "transcripts", path), encoding="utf-8") as f:
        return f.read()


def block(text, start, end=None):
    """전사에서 코드블록 하나를 뽑는다."""
    i = text.index(start) + len(start)
    j = text.index(end, i) if end else len(text)
    return text[i:j]


# ── 페르소나 A: 6턴, 리워크 4회, 전체 재출력 ─────────────────────
# 전사(persona_A_wasteful.md)의 실제 내용을 토큰으로 환산한다.
# "(... 600줄 재출력 ...)" 같은 축약 표기는 실제 파일 크기로 보정한다.
MEMO = open(os.path.join(HERE, "memo.html"), encoding="utf-8").read()
MEMO_TOK = tok(MEMO)

A_SYS = """현재 시각: 2026-08-15 14:32:07.412
세션 ID: sess_a3f9e21b-77c4-4e02-b1a9-0f2d6c8e5a13
요청 번호: #1

당신은 세계 최고의 시니어 풀스택 개발자입니다. 20년 경력의 전문가로서
사용자의 요청을 깊이 이해하고 최선의 코드를 작성해야 합니다.
항상 친절하고 상세하게 설명해 주세요. 코드를 작성하기 전에 먼저 어떤 접근을
취할 것인지 계획을 설명하고, 코드를 작성한 후에는 그 코드가 어떻게 동작하는지
단계별로 자세히 설명해 주세요. 그리고 마지막에는 전체 내용을 요약해 주세요.
사용자가 초보자일 수 있으므로 전문 용어는 풀어서 설명해 주시고,
가능하면 확장 가능하고 유지보수하기 좋은 구조로 작성해 주세요.
미래에 기능이 추가될 것을 고려해서 설계해 주시면 더욱 좋겠습니다.
베스트 프랙티스를 최대한 준수해 주세요.
답변은 반드시 한국어로 해 주시고, 생각하는 과정도 한국어로 진행해 주세요."""

B_SYS = """Senior full-stack engineer. Output code only.

Rules:
- No preamble, no plan narration, no post-hoc explanation, no summary.
- Comments only where intent is non-obvious.
- Implement exactly the spec. No speculative abstraction (YAGNI).
- If spec is ambiguous, ask one line. Do not guess.
- Think in English. Reply in Korean only for prose the user reads."""

A_SPEC = read("persona_A_wasteful.md")
B_SPEC = read("persona_B_frugal.md")

# B의 스펙 프롬프트 (턴1 유저 메시지) — 전사에서 실제로 추출
B_USER1 = block(B_SPEC, "**USER**\n\n```\n", "\n```\n\n**ASSISTANT**")
B_USER2 = block(B_SPEC[B_SPEC.index("## 턴 2"):], "**USER**\n\n```\n",
                "\n```\n\n**ASSISTANT**")
B_OUT2 = """@media(max-width:640px){
  #list{width:140px} .item p{display:none}
}"""

# A의 턴별 유저 메시지 (짧다 — 그게 문제의 시작)
A_USERS = [
    "메모장 좀 만들어줘",
    "아니 이렇게 복잡한 거 말고... 그냥 html 파일 하나로 되는 거",
    "디자인이 너무 밋밋한데 다크 테마로 해줘",
    "저장이 안 되는 것 같은데? 새로고침하면 사라져",
    "이제 저장은 되는데 목록에서 클릭해도 안 열려",
    "음... 그냥 처음부터 심플하게 다시 만들어줘. 이벤트버스 이런 거 다 빼고",
]

# A의 턴별 출력 토큰
# 턴1: React 20파일 과잉설계 + 계획서술 + 10단계해설 + 요약
# 턴2~5: 단일 HTML 600줄 전체 재출력 + 설명 3종세트
# 턴6: 최종본(=memo.html) + 설명
OVERSPEC = tok(block(A_SPEC, "## 턴 1", "## 턴 2"))   # 전사에 적힌 실제 분량
BIG_HTML = int(MEMO_TOK * 2.9)     # 이벤트버스·CSS변수·다크모드 등 과잉 버전
EXPLAIN = 900                       # 계획서술+단계별해설+요약 3종세트 (턴당)

A_OUTPUTS = [
    OVERSPEC + BIG_HTML // 3,       # 턴1: 구조도 + 파일 일부 + 설명
    BIG_HTML + EXPLAIN,             # 턴2: 단일 HTML 전체 + 설명
    BIG_HTML + EXPLAIN,             # 턴3: 다크테마 → 전체 재출력
    BIG_HTML + EXPLAIN,             # 턴4: 저장 버그 → 전체 재출력
    BIG_HTML + EXPLAIN,             # 턴5: 클릭 버그 → 전체 재출력
    MEMO_TOK + EXPLAIN,             # 턴6: 최종본 + 설명
]
# 턴 성격별 사고량 (출력 길이에 비례시키지 않는다)
A_THINK = [THINK_DESIGN, THINK_DESIGN, THINK_REWORK,
           THINK_REWORK, THINK_REWORK, THINK_DESIGN]

B_OUTPUTS = [MEMO_TOK, tok(B_OUT2)]
B_THINK = [THINK_DESIGN, THINK_TWEAK]


def simulate(name, sys_prompt, users, outputs, thinks, *, effort,
             ko_thinking, cache_ok, m, legacy=False, ko_multiplier=1.0):
    """매 턴 보이는 이력을 전부 재전송한다는 비용 모형 (API 제어 흐름·사고 이력은 별도)."""
    rows = []
    hist = 0
    tot_in = tot_out = tot_think = 0.0
    cost = 0.0
    sys_tok = tok(sys_prompt)

    for i, (u, o, base_think) in enumerate(zip(users, outputs, thinks)):
        u_tok = tok(u)
        inp = sys_tok + hist + u_tok

        # 사고 토큰: 턴 난이도별 배정값 × effort 감쇄 (출력 길이와 무관)
        think = base_think * effort
        if ko_thinking:
            think *= KO_PENALTY if legacy else ko_multiplier  # 명시적 감도 가정, 실측 페널티 아님

        # 캐싱: 프리픽스가 고정이면 첫 턴 write, 이후 read
        if cache_ok and (legacy or pricing.cache_eligible(m, sys_tok)):
            cached = sys_tok
            fresh = inp - cached
            rate = m.cache_write if i == 0 else m.cache_read
            in_cost = (fresh * m.inp + cached * m.inp * rate) / 1e6
        else:
            # 맨 앞 동적값 → 매 턴 캐시 미스. write 프리미엄만 계속 지불
            write = m.cache_write if (legacy or (not cache_ok and pricing.cache_eligible(m, inp))) else 1.0
            in_cost = (inp * m.inp * write) / 1e6
            cached = 0

        out_cost = (o + think) * m.out / 1e6
        cost += in_cost + out_cost

        rows.append({
            "turn": i + 1, "in": inp, "cached": cached,
            "out": o, "think": round(think),
            "cost": in_cost + out_cost,
        })
        tot_in += inp
        tot_out += o
        tot_think += think
        hist += u_tok + o          # 다음 턴 입력에 누적

    return {
        "name": name, "rows": rows, "turns": len(users),
        "in": tot_in, "out": tot_out, "think": tot_think,
        "cost": cost, "sys": sys_tok,
    }


def bar(v, mx, w=34, ch="█"):
    n = int(round(v / mx * w)) if mx else 0
    return ch * max(n, 1 if v > 0 else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet", choices=list(pricing.MODELS))
    ap.add_argument("--scenario", choices=["current", "legacy"], default="current")
    ap.add_argument("--ko-multiplier", type=float, default=1.0,
                    help="assumed thinking multiplier, NOT learned from tokenizer counts")
    ap.add_argument("--write-results", help="write the chosen scenario and assumptions to JSON")
    a = ap.parse_args()
    m = pricing.get(a.model)

    A = simulate("A 김낭비 (원칙 0개)", A_SYS, A_USERS, A_OUTPUTS, A_THINK,
                 effort=1.0, ko_thinking=True, cache_ok=False, m=m, legacy=a.scenario == "legacy", ko_multiplier=a.ko_multiplier)
    B = simulate("B 박절약 (원칙 전부)", B_SYS, [B_USER1, B_USER2], B_OUTPUTS,
                 B_THINK, effort=EFFORT_LOW, ko_thinking=False,
                 cache_ok=True, m=m, legacy=a.scenario == "legacy", ko_multiplier=a.ko_multiplier)

    if a.write_results:
        import json
        from pathlib import Path
        result = {"evidence_type": "cost_scenario", "scenario": a.scenario,
                  "note": "API policy A/B 아님. legacy는 최소길이 미달 캐싱·한국어 사고 1.44 가정을 재현할 뿐.",
                  "price_model": m.name, "price_input": m.inp, "price_output": m.out,
                  "ko_thinking_multiplier": KO_PENALTY if a.scenario == "legacy" else a.ko_multiplier,
                  "effort_low_multiplier": EFFORT_LOW, "expanded_html_multiplier": 2.9,
                  "memo_tok": f"{MEMO_TOK:,}", "ratio": f"{A['cost']/B['cost']:.1f}",
                  "year_gap": f"{(A['cost']-B['cost'])*1760*12:,.0f}",
                  "A": A, "B": B}
        for name, case in (("a", A), ("b", B)):
            for key, field in (("in", "in"), ("out", "out"), ("th", "think")):
                result[name + "_" + key] = f"{case[field]:,.0f}"
            result[name + "_cost"] = f"{case['cost']:.4f}"
        Path(a.write_results).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    W = 86
    print("=" * W)
    print("  같은 메모장, 두 가지 습관 — 토큰·비용 시나리오 비교")
    print("=" * W)
    print(f"  모델        {m.name}  (입력 ${m.inp}/1M · 출력 ${m.out}/1M · "
          f"캐시읽기 {m.cache_read}×)")
    print(f"  결과물      memo.html  {MEMO_TOK:,} tok  (양쪽 동일)")
    print(f"  토큰 계측   실파일 인코딩 + 출력 확대·턴 수 가정")
    print(f"  사고 추정   턴 난이도별 배정 "
          f"(설계 {THINK_DESIGN} · 리워크 {THINK_REWORK} · 수정 {THINK_TWEAK})")
    print(f"              사고량은 관측 보장이 없는 가정 (300 포함, 승수 적용 후 범위 밖 가능)")

    for P in (A, B):
        print()
        print("─" * W)
        print(f"  {P['name']}   —   {P['turns']}턴")
        print("─" * W)
        print(f"  {'턴':<4}{'입력':>10}{'캐시':>9}{'출력':>9}"
              f"{'사고':>9}{'비용':>11}")
        for r in P["rows"]:
            print(f"  {r['turn']:<4}{r['in']:>10,}{r['cached']:>9,}"
                  f"{r['out']:>9,}{r['think']:>9,}{r['cost']:>11.4f}")
        print(f"  {'계':<4}{P['in']:>10,.0f}{'':>9}{P['out']:>9,.0f}"
              f"{P['think']:>9,.0f}{P['cost']:>11.4f}")

    print()
    print("=" * W)
    print("  항목별 비교")
    print("=" * W)
    mx = max(A["in"], A["out"] + A["think"])
    items = [
        ("입력 토큰", A["in"], B["in"]),
        ("출력 토큰(응답)", A["out"], B["out"]),
        ("사고 토큰", A["think"], B["think"]),
        ("과금 출력계", A["out"] + A["think"], B["out"] + B["think"]),
    ]
    print(f"  {'항목':<16}{'A 김낭비':>13}{'B 박절약':>13}{'절감':>9}")
    for label, av, bv in items:
        cut = (1 - bv / av) * 100 if av else 0
        print(f"  {label:<16}{av:>13,.0f}{bv:>13,.0f}{cut:>8.0f}%")
        print(f"  {'':<4}A {bar(av, mx, 30)}")
        print(f"  {'':<4}B {bar(bv, mx, 30)}")
        print()

    print()
    ratio = A["cost"] / B["cost"]
    print(f"  {'비용':<16}{'$'+format(A['cost'],'.4f'):>13}"
          f"{'$'+format(B['cost'],'.4f'):>13}"
          f"{(1-B['cost']/A['cost'])*100:>8.0f}%")
    print(f"  {'턴 수':<16}{A['turns']:>13}{B['turns']:>13}")
    print()
    print(f"  ★ 같은 목표 결과물을 가정할 때 A 비용이 B보다 {ratio:.1f}배 비싸다.")

    # 팀 단위
    print()
    print("─" * W)
    print("  팀 단위 환산 (10명 × 하루 8건 × 22일 = 1,760건/월)")
    print("─" * W)
    N = 1760
    am, bm = A["cost"] * N, B["cost"] * N
    print(f"  A 김낭비   월 ${am:,.0f}   연 ${am*12:,.0f}")
    print(f"  B 박절약   월 ${bm:,.0f}   연 ${bm*12:,.0f}")
    print(f"  차액       월 ${am-bm:,.0f}   연 ${(am-bm)*12:,.0f}")

    # 어디서 벌어졌나
    print()
    print("─" * W)
    print("  차이의 출처 분해")
    print("─" * W)
    rework = sum(r["out"] + r["think"] for r in A["rows"][1:5])
    explain_tot = EXPLAIN * 5
    print(f"  ① 리워크 4회(턴2~5) 전체 재출력      "
          f"{rework:>10,.0f} tok  ← 가장 큰 덩어리")
    print(f"  ② 설명 3종세트(계획·해설·요약)       "
          f"{explain_tot:>10,.0f} tok")
    print(f"  ③ 한국어 사고 승수 가정 = {KO_PENALTY if a.scenario == 'legacy' else a.ko_multiplier} (hidden 사고의 실측 이점 아님)")
    print(f"  ④ 캐시 미스(맨 앞 동적값)            "
          f"{'':>10}      A는 적격 길이일 때만 쓰기 프리미엄 (legacy는 길이 무시)")
    print(f"  ⑤ 과잉설계(안 쓸 코드) 생성·재전송   "
          f"{OVERSPEC:>10,.0f} tok  ← 턴1에서만")

    print()
    print("─" * W)
    print("  다른 시나리오와의 범위 비교 (독립 검증 아님)")
    print("─" * W)
    rw_only = A["cost"] / B["cost"]
    print(f"  exp09-C  리워크 6사이클 = 1사이클의 16.6배")
    print(f"           → 이 시뮬레이션의 리워크 축만 보면 A는 6턴, B는 2턴")
    print(f"  exp06 스택 적층 85.825% 산술 (검증된 상한 아님)")
    print(f"           → 여기는 리워크 제거까지 포함하므로 "
          f"{(1-B['cost']/A['cost'])*100:.0f}%가 더 크다. 축이 다르다.")
    print(f"  exp02 스펙 주입 약 66% 시나리오 (리워크 제외, 단일 요청)")
    print(f"           → 본 비교는 리워크 4회를 포함한 세션 전체라 배수가 커진다.")
    print()
    print(f"  ⚠️ {rw_only:.1f}배는 '6턴 세션'과 '수정 1회를 포함한 2턴 세션'의 비교다.")
    print(f"     턴 감소·품질 동등성은 관측한 것이 아니다. 단일 레버의 인과 효과도 아니다.")
    print(f"     발표에서는 '이 가정하의 예시 계산'으로 말할 것. 검증된 상한 아님.")

    print()
    print("=" * W)
    print("  결론")
    print("=" * W)
    print("  · 같은 memo.html을 목표 산출물로 두었다. 독립된 실제 두 세션의 성공을 측정하지 않았다.")
    print("  · 비용 차이는 가정한 턴 수·출력량·사고량·캐시 조건의 결과다.")
    print("    영어 사고 · verbosity low · 동적값을 뒤로.")
    print(f"  · 이 시나리오 환산 차액은 연 ${(am-bm)*12:,.0f}다 (10인 팀 기준).")
    print("=" * W)


if __name__ == "__main__":
    main()
