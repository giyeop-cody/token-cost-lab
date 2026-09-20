# -*- coding: utf-8 -*-
"""
실험 09 — DRY 원칙을 토큰 경제로 번역하면 (주장 ② 심화)

검증 대상 (사용자가 정리한 DRY 5항목):
  A. 같은 코드 재작성 최소화
  B. 반복되는 컨텍스트 최소화
  C. 반복되는 리워크 최소화
  D. 같은 로직은 한 군데서
  E. 같은 프롬프트는 최소화

결론 미리:
  A·C·D 는 그대로 참. B·E 는 **방향은 맞지만 처방이 틀리다.**
  코드에서 DRY는 "중복을 제거하라"지만, 토큰 경제에서 제거할 수 없는 반복은
  **제거(압축)와 고정(캐싱)을 병용할 수 있다.** 적은 반복이 아니라 '변주'다.

실행:
  python experiments/exp09_dry.py
  python experiments/exp09_dry.py --model opus

출처:
  프롬프트 캐싱 사양 (반복을 할인으로 바꾸는 근거)
    Anthropic — https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
      (읽기 0.1x, 쓰기 1.25x, 최소 1,024 토큰, 프리픽스 단위 매칭)
    OpenAI    — https://platform.openai.com/docs/guides/prompt-caching
  Regmi & Pun, "GPT Semantic Cache" — https://arxiv.org/abs/2411.05276
    (의미가 같은 질의를 매칭해 API 호출 최대 68.8% 감소 → E 항목의 근거)
  Anthropic, "Effective context engineering for AI agents"
    https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
    (context rot — 중복 컨텍스트는 비용뿐 아니라 정확도도 갉아먹는다)
  전체 목록: ../SOURCES.md
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab import pricing, report  # noqa: E402

EVIDENCE = "시나리오: 토큰·턴·효과 가정의 비용 계산. 실제 정책 A/B나 품질 동등 절감 실측 아님."


def sec_a(m, calls):
    """A. 같은 코드 재작성 최소화 — 출력 토큰 직격."""
    report.section("A. 같은 코드 재작성 최소화")

    file_tok = 5000        # 400줄짜리 모듈
    edits = 10             # 수정 10회
    diff_tok = 300         # 실제 바뀌는 부분

    full = file_tok * edits
    diff = diff_tok * edits

    c_full = pricing.cost(m, 0, full)
    c_diff = pricing.cost(m, 0, diff)

    report.table(
        ["방식", "1회 출력", "10회 누적", "비용"],
        [["파일 전체 재출력", f"{file_tok:,}", f"{full:,}", pricing.usd(c_full)],
         ["바뀐 부분만 출력", f"{diff_tok:,}", f"{diff:,}", pricing.usd(c_diff)]],
        ["l", "r", "r", "r"],
    )
    print()
    report.kv("절감", f"{(1 - c_diff / c_full) * 100:.0f}%",
              f"(연 {calls}회 기준 {pricing.usd((c_full - c_diff) * calls / edits, 0)})")
    print("  → '전체 파일을 다시 써줘'가 가장 비싼 한마디다.")
    print("     같은 코드를 두 번 만들지 않는 것 = 출력 토큰을 두 번 사지 않는 것.")
    return c_full - c_diff


def sec_b(m):
    """B. 반복되는 컨텍스트 — ★ 여기서 DRY가 뒤집힌다."""
    report.section("B. 반복되는 컨텍스트 최소화  ← 처방이 틀린 항목")

    prefix = 12000
    calls = 100
    # 전제: 프리픽스 12,000토큰이 100% 고정이고 100% 적중하는 상한 조건.
    # 실험 03(-62%)은 가변부가 섞인 현실 조건이라 수치가 낮다. 둘은 모순이 아니라
    # 서로 다른 가정 시나리오다. 실측 절감률이 아니다.

    # ① 그냥 매번 보낸다
    naive = pricing.cost(m, prefix * calls, 0)

    # ② 반복을 '제거'하려고 프리픽스를 절반으로 줄인다 (요약·삭제)
    slim = pricing.cost(m, (prefix // 2) * calls, 0)

    # ③ 반복을 그대로 두되 완전히 동일하게 고정 → 캐시
    #    첫 호출은 쓰기(1.25x), 이후 99회는 읽기(0.1x)
    eligible = pricing.cache_eligible(m, prefix)
    write = prefix * m.inp * (m.cache_write if eligible else 1.0) / 1e6
    reads = prefix * m.inp * (m.cache_read if eligible else 1.0) * (calls - 1) / 1e6
    cached = write + reads

    # ④ 반복은 있는데 앞에 타임스탬프가 붙어 매번 미스 (최악)
    broken = prefix * m.inp * (m.cache_write if eligible else 1.0) * calls / 1e6
    compressed = prefix // 2
    slim_cache_ok = pricing.cache_eligible(m, compressed)
    slim_cached = compressed * m.inp * (m.cache_write + (calls-1)*m.cache_read) / 1e6 if slim_cache_ok else slim

    rows = [
        ["① 매번 그대로 전송", f"{prefix * calls:,}", pricing.usd(naive), "기준"],
        ["② 절반으로 요약·삭제", f"{prefix // 2 * calls:,}", pricing.usd(slim),
         f"{(1 - slim / naive) * 100:.0f}%"],
        ["③ 그대로 두고 캐싱", f"{prefix * calls:,}", pricing.usd(cached),
         f"{(1 - cached / naive) * 100:.0f}%"],
        ["④ 압축 + 고정 + 캐싱", f"{compressed * calls:,}", pricing.usd(slim_cached), f"{(1-slim_cached/naive)*100:.0f}%"],
        ["⑤ 앞에 동적값 → 매번 미스", f"{prefix * calls:,}",
         pricing.usd(broken), f"{(1 - broken / naive) * 100:+.0f}%"],
    ]
    report.table(["전략", "입력 토큰", "비용", "절감"], rows, ["l", "r", "r", "r"])

    print()
    print("  ★ 압축과 캐싱은 함께 적용할 수 있다. 압축 비용·품질 손실·TTL은 이 계산 밖이다.")
    print(f"     ② {pricing.usd(slim)}  vs  ③ {pricing.usd(cached)}"
          f"  →  {slim / cached:.1f}배 차이")
    print()
    print("  코드의 DRY는 '중복을 지워라'다. 토큰의 DRY는 다르다:")
    print("    지울 수 있는 반복은 지우고,")
    print("    지울 수 없는 반복은 **한 글자도 바꾸지 말고 고정**해서 캐시에 태운다.")
    print("    적은 반복이 아니라 '변주(variation)'다.")
    print()
    print("  ④가 그 증거다. 같은 12,000토큰을 보내면서 앞에 타임스탬프 하나 붙였을 뿐인데")
    print(f"    아무것도 안 한 ①보다 {(broken / naive - 1) * 100:.0f}% 더 낸다.")
    return naive, cached


def sec_c(m):
    """C. 반복되는 리워크 최소화 — 턴 수의 2차 함수."""
    report.section("C. 반복되는 리워크 최소화")

    base = 3000        # 초기 컨텍스트
    per = 700          # 턴당 누적 이력
    out = 500          # 턴당 출력

    def loop(turns):
        tot = 0.0
        for t in range(1, turns + 1):
            tot += pricing.cost(m, base + per * (t - 1), out)
        return tot

    rows = []
    prev = None
    for cyc, turns in [("1사이클 (스펙 있음)", 8), ("2사이클", 16),
                       ("4사이클 (감으로 시작)", 32), ("6사이클", 48)]:
        c = loop(turns)
        rows.append([cyc, f"{turns}턴", pricing.usd(c),
                     "-" if prev is None else f"{c / prev:.1f}배"])
        prev = c if prev is None else prev
    report.table(["리워크", "누적 턴", "비용", "1사이클 대비"], rows,
                 ["l", "r", "r", "r"])

    one, six = loop(8), loop(48)
    print()
    report.kv("6사이클 / 1사이클", f"{six / one:.1f}배",
              "턴이 6배면 비용은 6배가 아니다")
    print("  → 리워크는 '한 번 더 시키는 것'이 아니라, 그때까지의 대화 전체를")
    print("     다시 사기 시작하는 것이다. 이력이 매 턴 재전송되기 때문.")
    return one, six


def sec_d(m):
    """D. 같은 로직은 한 군데서 — 중복은 컨텍스트와 출력 양쪽을 곱한다."""
    report.section("D. 같은 로직은 한 군데서")

    logic = 800        # 로직 한 벌
    copies = 3         # 복붙된 곳
    fixes = 5          # 이 로직을 고치는 횟수

    # 단일 출처: 읽을 것도 한 벌, 고칠 것도 한 벌
    single_in = logic * fixes
    single_out = 300 * fixes

    # 복제: 3곳을 다 읽어야 하고, 3곳을 다 고쳐야 한다
    dup_in = logic * copies * fixes
    dup_out = 300 * copies * fixes

    c_single = pricing.cost(m, single_in, single_out)
    c_dup = pricing.cost(m, dup_in, dup_out)

    report.table(
        ["구조", "입력", "출력", f"{fixes}회 수정 비용"],
        [["단일 출처 1곳", f"{single_in:,}", f"{single_out:,}", pricing.usd(c_single)],
         [f"복붙 {copies}곳", f"{dup_in:,}", f"{dup_out:,}", pricing.usd(c_dup)]],
        ["l", "r", "r", "r"],
    )
    print()
    report.kv("복제의 대가", f"{c_dup / c_single:.1f}배", f"(복제 수 {copies}에 정비례)")
    print("  → 복붙은 만들 때가 아니라 **고칠 때마다** 청구된다.")
    print("     게다가 한 곳만 고치고 두 곳을 놓치면 그 디버깅이 또 리워크(C)다.")
    return c_dup - c_single


def sec_e(m):
    """E. 같은 프롬프트 최소화 — 중복 '호출'은 없애고, 중복 '내용'은 고정한다."""
    report.section("E. 같은 프롬프트는 최소화  ← 두 가지가 섞여 있는 항목")

    calls = 10000
    inp, out = 1500, 600
    dup_rate = 0.30       # 30%는 사실상 같은 질문

    full = pricing.cost(m, inp * calls, out * calls)

    # ① 의미가 같은 질의를 캐시에서 반환 → 호출 자체가 사라진다
    live = int(calls * (1 - dup_rate))
    semantic = pricing.cost(m, inp * live, out * live)

    # ② 같은 질문인데 표현만 달라 캐시가 안 걸리는 경우 = 절감 0
    varied = full

    report.table(
        ["상황", "실제 호출", "비용", "절감"],
        [["중복 30%를 그냥 다 호출", f"{calls:,}", pricing.usd(full, 2), "-"],
         ["의미 동일 → 시맨틱 캐시 히트", f"{live:,}",
          pricing.usd(semantic, 2), f"{(1 - semantic / full) * 100:.0f}%"],
         ["같은 질문, 표현만 다름 → 미스", f"{calls:,}",
          pricing.usd(varied, 2), "0%"]],
        ["l", "r", "r", "r"],
    )
    print()
    print("  이 항목은 두 개가 섞여 있다. 분리해야 한다:")
    print("    · 중복 '호출'  → 없애라. 답이 같은 질문을 두 번 사지 마라. (-30%)")
    print("    · 중복 '내용'  → 없애지 말고 **똑같이 고정**하라. 캐시가 할인해준다.")
    print()
    print("  둘 다 적이 같다: '거의 같지만 미묘하게 다른 것'.")
    print("  캐시는 완전 일치에만 반응하므로, 어중간한 변주가 가장 비싸다.")
    return full - semantic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=pricing.DEFAULT)
    ap.add_argument("--calls", type=int, default=1760, help="월 호출 수 (A절 환산용)")
    args = ap.parse_args()
    print(EVIDENCE)
    m = pricing.get(args.model)

    report.title("실험 09 — DRY를 토큰 경제로 번역하면")
    report.kv("모델", m.name,
              f"(입력 ${m.inp}/1M · 출력 ${m.out}/1M · 캐시읽기 {m.cache_read}x)")

    sec_a(m, args.calls)
    naive, cached = sec_b(m)
    one, six = sec_c(m)
    sec_d(m)
    sec_e(m)

    # ── 판정 요약
    report.section("판정")
    report.table(
        ["#", "DRY 항목", "판정", "근거"],
        [["A", "같은 코드 재작성 최소화", "참", "전체 재출력 대비 -94%"],
         ["B", "반복되는 컨텍스트 최소화", "조건부",
          f"압축+캐싱 병용 가능; 원문 캐싱만도 -{(1 - cached / naive) * 100:.0f}% (기본 시나리오)"],
         ["C", "반복되는 리워크 최소화", "참", f"6사이클은 1사이클의 {six / one:.1f}배"],
         ["D", "같은 로직은 한 군데서", "참", "복붙 3곳 = 수정 비용 3배"],
         ["E", "같은 프롬프트는 최소화", "조건부",
          "중복 호출은 제거, 중복 내용은 고정"]],
        ["l", "l", "l", "l"],
    )

    report.verdict(
        "DRY를 지키면 토큰이 절약된다",
        "참 — 단, 코드의 DRY와 컨텍스트의 DRY는 처방이 반대다",
        "코드·로직·리워크의 중복은 '제거'가 답이다(A·C·D). "
        "그러나 시스템 프롬프트처럼 제거할 수 없는 반복은 '고정'이 답이다(B·E). "
        "토큰 경제에서 비싼 것은 반복이 아니라 변주다. "
        "똑같이 반복되면 캐시가 90%를 깎아주지만, 변경 지점 이전의 캐시 가능한 공통 프리픽스는 남을 수 있다.",
    )


if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
