#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_deck.py — 슬라이드에 박힌 숫자를 원자료로 다시 계산해서 대조한다.

이 저장소의 실패 유형은 "계산이 틀렸다"가 아니라
**"원자료는 맞는데 슬라이드가 다른 말을 한다"** 였다.
2026-08-15 검증에서 발견된 12건 중 7건이 이 범주였고, 전부 아래 테스트로 잡힌다.

  · 원자료(JSONL)에서 재계산한 값 vs 슬라이드 표기값
  · 표의 행 합계 vs 표기된 합계          (슬라이드 5 행 누락 유형)
  · 슬라이드 간 동일 지표의 일관성        (슬라이드 16 vs 17 기준선 유형)
  · 단가 가정을 바꿨을 때의 민감도        (240× vs 149× 유형)
  · 원자료 파일 존재 여부                 (없는 파일을 각주로 안내한 유형)

사용:
    python tools/verify_deck.py                 # 전체 검사
    python tools/verify_deck.py --verbose       # 통과 항목까지 전부 출력
    python tools/verify_deck.py --pptx ../토큰_절약_발표.pptx   # 덱 텍스트까지 대조

종료 코드: 실패 0건이면 0, 하나라도 있으면 1 (CI에 그대로 물릴 수 있다)
"""
import argparse
import json
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # token-cost-lab/
# 덱(pptx)의 위치는 브랜치에 따라 다르다.
#   presentation 브랜치 → ROOT/presentation/  (저장소 안)
#   main 브랜치         → 저장소에 없음        (발표 패키지 쪽)
# 둘 다 없으면 실패가 아니라 SKIP 처리한다.
PKG = os.path.dirname(ROOT)                       # 발표 패키지 루트 (저장소 밖)
DECK_NAME = "토큰_절약_발표.pptx"


def find_deck():
    for cand in (os.path.join(ROOT, "presentation", DECK_NAME),
                 os.path.join(PKG, DECK_NAME)):
        if os.path.exists(cand):
            return cand
    return os.path.join(ROOT, "presentation", DECK_NAME)

# 슬라이드 비용 환산에 쓰인 단가 (gemini-25: $1.25/$10 per 1M)
IN_R, OUT_R = 1.25 / 1e6, 10.0 / 1e6
# 실제 호출된 모델(flash-lite)의 공식 단가 — 민감도 확인용
ALT_IN, ALT_OUT = 0.10 / 1e6, 0.40 / 1e6

TOL = 0.02          # 상대 오차 2%까지 허용 (반올림 표기 흡수)
ANSWER = 38.016     # thinking_sweep 문제의 정답
ANSWER_TOL = 0.05

results = []        # (level, name, ok, detail)


def check(name, ok, detail="", level="FAIL"):
    # SKIP은 '통과'가 아니다. 의존성이 없어 검사를 못 돌린 것을 통과로 세면
    # CI가 초록불인데 실제로는 아무것도 검증하지 않은 상태가 된다.
    if level == "SKIP":
        results.append(("SKIP", name, ok, detail))
    else:
        results.append((level if not ok else "PASS", name, ok, detail))
    return ok


def close(a, b, tol=TOL):
    if b == 0:
        return abs(a) < 1e-12
    return abs(a - b) / abs(b) <= tol


def load(path):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def cost(r, i=IN_R, o=OUT_R):
    return r["prompt"] * i + (r["thoughts"] + r["cands"]) * o


# ────────────────────────────────────────────────────────────────
# 1. 슬라이드 7 — N=80 라이브 벤치
# ────────────────────────────────────────────────────────────────
SLIDE7 = {
    # task, lang: (사고, 응답, 글자, 호출당비용, $/1000자)
    ("explain", "en"): (697, 144, 822, 0.008441, 0.01029),
    ("explain", "ko"): (967, 181, 366, 0.011515, 0.03116),
    ("reason", "en"): (1616, 214, 570, 0.018374, 0.03246),
    ("reason", "ko"): (1116, 210, 305, 0.013375, 0.04419),
}
SLIDE7_RATIO = {"explain": 3.03, "reason": 1.36}


def verify_slide7():
    rows = load("results/live_lang_thinking.jsonl")
    if not check("슬라이드7 원자료 존재 (live_lang_thinking.jsonl)", rows is not None,
                 "파일 없음 — 재현 각주가 가리키는 파일이 실제로 있어야 한다"):
        return
    check("슬라이드7 표본 수 80", len(rows) == 80, f"실제 {len(rows)}행")
    check("슬라이드7 절단 표본 0건",
          all(r.get("finish") == "STOP" for r in rows),
          "finish != STOP 인 행이 있으면 분량 비교가 오염된다")
    check("슬라이드7 모델 단일",
          len({r.get("model") for r in rows}) == 1,
          f"모델 {sorted({r.get('model') for r in rows})} — 폴백 혼입 시 비교 무의미")

    for (task, lang), (th, ca, ch, cc, per1k) in SLIDE7.items():
        g = [r for r in rows if r["task"] == task and r["lang"] == lang]
        if not check(f"슬라이드7 {task}/{lang} 표본 존재", bool(g)):
            continue
        tag = f"{task}/{lang}"
        check(f"슬라이드7 {tag} 사고토큰 {th}",
              close(st.mean(r["thoughts"] for r in g), th),
              f"재계산 {st.mean(r['thoughts'] for r in g):.0f}")
        check(f"슬라이드7 {tag} 응답토큰 {ca}",
              close(st.mean(r["cands"] for r in g), ca),
              f"재계산 {st.mean(r['cands'] for r in g):.0f}")
        check(f"슬라이드7 {tag} 글자수 {ch}",
              close(st.mean(r["chars"] for r in g), ch),
              f"재계산 {st.mean(r['chars'] for r in g):.0f}")
        check(f"슬라이드7 {tag} 호출당 비용 ${cc}",
              close(st.mean(cost(r) for r in g), cc),
              f"재계산 ${st.mean(cost(r) for r in g):.6f}")
        check(f"슬라이드7 {tag} $/1,000자 {per1k}",
              close(st.mean(cost(r) / r["chars"] * 1000 for r in g), per1k),
              f"재계산 ${st.mean(cost(r)/r['chars']*1000 for r in g):.5f}")

    for task, ratio in SLIDE7_RATIO.items():
        en = [r for r in rows if r["task"] == task and r["lang"] == "en"]
        ko = [r for r in rows if r["task"] == task and r["lang"] == "ko"]
        got = (st.mean(cost(r) / r["chars"] * 1000 for r in ko) /
               st.mean(cost(r) / r["chars"] * 1000 for r in en))
        check(f"슬라이드7 {task} 정규화 배수 {ratio}×", close(got, ratio),
              f"재계산 {got:.2f}×")


# ────────────────────────────────────────────────────────────────
# 2. 슬라이드 25 — 사고 예산 스윕
# ────────────────────────────────────────────────────────────────
SLIDE25 = {
    # label: (사고, 응답, 비용, 배수, 정답률)
    "미지정(기본)": (0, 6, 0.000155, 1.0, 6),
    "끔 (0)":       (0, 6, 0.000158, 1.0, 5),
    "512":          (142, 6, 0.001570, 10.1, 2),
    "2048":         (1114, 6, 0.011302, 72.9, 6),
    "자동 (-1)":    (3704, 6, 0.037203, 240.0, 6),
}


def n_correct(rows):
    """응답 문자열에서 첫 숫자를 뽑아 정답(±0.05) 개수를 센다."""
    n = 0
    for r in rows:
        m = re.findall(r"[\d.]+", (r.get("text") or "").replace(",", ""))
        if m:
            try:
                if abs(float(m[0]) - ANSWER) <= ANSWER_TOL:
                    n += 1
            except ValueError:
                pass
    return n


def verify_slide25():
    rows = load("results/thinking_sweep.jsonl")
    if not check("슬라이드25 원자료 존재 (thinking_sweep.jsonl)", rows is not None):
        return
    check("슬라이드25 표본 수 30", len(rows) == 30, f"실제 {len(rows)}행")

    groups = {}
    for r in rows:
        groups.setdefault(r["label"], []).append(r)

    base = None
    for label, (th, ca, cc, mult, ncorr) in SLIDE25.items():
        g = groups.get(label)
        if not check(f"슬라이드25 '{label}' 표본 존재", bool(g)):
            continue
        c = st.mean(cost(r) for r in g)
        if base is None:
            base = c
        check(f"슬라이드25 '{label}' 사고토큰 {th}",
              close(st.mean(r["thoughts"] for r in g), th, 0.03),
              f"재계산 {st.mean(r['thoughts'] for r in g):.0f}")
        check(f"슬라이드25 '{label}' 비용 ${cc}", close(c, cc),
              f"재계산 ${c:.6f}")
        check(f"슬라이드25 '{label}' 배수 {mult}×", close(c / base, mult, 0.03),
              f"재계산 {c/base:.1f}×")
        # ★ 이 검사가 1-1·1-2 치명 오류를 잡는다
        got = n_correct(g)
        check(f"슬라이드25 '{label}' 정답률 {ncorr}/6", got == ncorr,
              f"재계산 {got}/6 — 응답: {sorted({(r.get('text') or '').strip() for r in g})}")

    # 문자열이 '전부 동일'하다는 주장은 거짓이어야 한다 (재발 방지 가드)
    allsame = {(r.get("text") or "").strip() for r in rows}
    check("슬라이드25 '답변 문자열이 전부 동일' 주장 금지 가드",
          len(allsame) > 1,
          f"실제 서로 다른 응답 {len(allsame)}종 — '같은 숫자'가 아니라 '같은 정답률'로 말할 것")

    # 사고 비중
    on = [r for r in rows if r["thoughts"] > 0]
    share = sum(r["thoughts"] for r in on) / sum(r["thoughts"] + r["cands"] for r in on)
    check("슬라이드25 사고 비중 99%", close(share, 0.99, 0.02),
          f"재계산 {share*100:.1f}%")

    # 단가 민감도 — 240×는 gemini-25 단가 가정에 의존한다
    g_auto, g_base = groups.get("자동 (-1)"), groups.get("미지정(기본)")
    if g_auto and g_base:
        alt = (st.mean(cost(r, ALT_IN, ALT_OUT) for r in g_auto) /
               st.mean(cost(r, ALT_IN, ALT_OUT) for r in g_base))
        check("슬라이드25 단가 민감도 명시 필요 (flash-lite 실단가 ≈149×)",
              close(alt, 149, 0.05),
              f"실단가 환산 {alt:.0f}× — 덱의 240×와 다르므로 전제를 밝혀야 한다",
              level="WARN")


# ────────────────────────────────────────────────────────────────
# 3. 표 내부 정합성 — 행 합계 (슬라이드 5 유형)
# ────────────────────────────────────────────────────────────────
def verify_tables():
    """슬라이드 5: 개별 행의 합이 표기된 합계와 일치하는가."""
    try:
        import tiktoken
    except ImportError:
        check("슬라이드5 토크나이저 검사", False, "tiktoken 없음", level="SKIP")
        return
    path = os.path.join(ROOT, "data", "sentence_pairs.json")
    if not check("슬라이드5 문장쌍 원본 존재", os.path.exists(path)):
        return
    pairs = json.load(open(path, encoding="utf-8"))
    o = tiktoken.get_encoding("o200k_base")
    c = tiktoken.get_encoding("cl100k_base")
    en_o = sum(len(o.encode(p["en"])) for p in pairs)
    ko_o = sum(len(o.encode(p["ko"])) for p in pairs)
    ko_c = sum(len(c.encode(p["ko"])) for p in pairs)

    check("슬라이드5 문장 6개 (합계 라벨과 일치)", len(pairs) == 6,
          f"실제 {len(pairs)}개 — 표에 6행이 모두 그려져야 한다")
    check("슬라이드5 EN o200k 합계 121", en_o == 121, f"재계산 {en_o}")
    check("슬라이드5 KO o200k 합계 174", ko_o == 174, f"재계산 {ko_o}")
    check("슬라이드5 KO cl100k 합계 269", ko_c == 269, f"재계산 {ko_c}")
    check("슬라이드5 o200k 배수 1.44×", close(ko_o / en_o, 1.44),
          f"재계산 {ko_o/en_o:.2f}×")


# ────────────────────────────────────────────────────────────────
# 4. 슬라이드 간 일관성 (슬라이드 16 vs 17 유형)
# ────────────────────────────────────────────────────────────────
def verify_caching_consistency():
    sys.path.insert(0, ROOT)
    try:
        from lab import pricing
    except ImportError:
        check("캐싱 일관성 검사", False, "lab.pricing 임포트 실패", level="SKIP")
        return
    m = pricing.get("sonnet")
    S, D, O, N = 20000, 1000, 1500, 100
    no_cache = N * pricing.cost(m, S + D, O)
    w = (S * m.inp * m.cache_write + D * m.inp + O * m.out) / 1e6
    r = (S * m.inp * m.cache_read + D * m.inp + O * m.out) / 1e6
    full = w + (N - 1) * r
    allmiss = N * w

    check("슬라이드16 캐시 없음 $8.55", close(no_cache, 8.55), f"재계산 ${no_cache:.2f}")
    check("슬라이드16 캐시 적용 $3.22", close(full, 3.22), f"재계산 ${full:.2f}")
    check("슬라이드16 절감 62%", close(1 - full / no_cache, 0.62, 0.03),
          f"재계산 {(1-full/no_cache)*100:.0f}%")
    # ★ 16과 17이 같은 기준선을 써야 한다
    check("슬라이드17 기준선 = 슬라이드16 '캐시 없음' ($8.55)",
          close(no_cache, 8.55),
          "17의 기준이 $10.05(=매번 미스)면 두 슬라이드가 다른 절감률을 말하게 된다")
    check("슬라이드17 '매번 미스' $10.05 = 미사용 대비 +18%",
          close(allmiss, 10.05) and close(allmiss / no_cache - 1, 0.18, 0.05),
          f"재계산 ${allmiss:.2f} ({(allmiss/no_cache-1)*100:+.0f}%)")
    check("슬라이드17 안티패턴 3.1배", close(allmiss / full, 3.1, 0.03),
          f"재계산 {allmiss/full:.2f}배")
    prem = S * m.inp * (m.cache_write - 1) / 1e6
    save = S * m.inp * (1 - m.cache_read) / 1e6
    check("슬라이드17 손익분기 0.28회", close(prem / save, 0.28, 0.05),
          f"재계산 {prem/save:.2f}회")


# ────────────────────────────────────────────────────────────────
# 5. 단위 검사 (슬라이드 2 유형)
# ────────────────────────────────────────────────────────────────
def verify_units():
    sys.path.insert(0, ROOT)
    from lab import pricing
    m = pricing.get("sonnet")
    cached_10k = 10000 * m.inp * m.cache_read / 1e6 * 100   # 센트
    out_10k = 10000 * m.out / 1e6 * 100
    check("슬라이드2 '10,000토큰 = 캐시입력 0.3센트'", close(cached_10k, 0.3, 0.05),
          f"재계산 {cached_10k:.2f}센트")
    check("슬라이드2 '10,000토큰 = 출력 15센트'", close(out_10k, 15.0, 0.05),
          f"재계산 {out_10k:.2f}센트")
    check("슬라이드2 캐시입력 대비 출력 50배", close(out_10k / cached_10k, 50, 0.02),
          f"재계산 {out_10k/cached_10k:.0f}배")


# ────────────────────────────────────────────────────────────────
# 6. 에이전트 루프 2차 함수 (슬라이드 18)
# ────────────────────────────────────────────────────────────────
def verify_agent_loop():
    """exp04를 재구현하지 않고 직접 임포트한다 —
    검사기가 자기만의 모델을 들고 있으면 그 자체가 또 하나의 진실 공급원이 된다."""
    sys.path.insert(0, ROOT)
    import importlib.util
    from lab import pricing
    p = os.path.join(ROOT, "experiments", "exp04_agent_loop_sdd.py")
    if not check("슬라이드18 exp04 스크립트 존재", os.path.exists(p)):
        return
    spec = importlib.util.spec_from_file_location("_exp04", p)
    e4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(e4)
    m = pricing.get("sonnet")

    def sess(T):
        return e4.naive_loop(m, T, 8000, 2000, 800)[0]

    check("슬라이드18 20턴 $2.32", close(sess(20), 2.32), f"재계산 ${sess(20):.2f}")
    check("슬라이드18 50턴 $12.09", close(sess(50), 12.09), f"재계산 ${sess(50):.2f}")
    ratio = sess(20) / sess(10)
    check("슬라이드18 '턴 2배 = 약 3배' (10→20턴)", 2.8 <= ratio <= 3.3,
          f"재계산 {ratio:.2f}배 — '정확히 3배'로 단정하지 말 것")


# ────────────────────────────────────────────────────────────────
# 7. 각주가 가리키는 파일이 실제로 있는가
# ────────────────────────────────────────────────────────────────
def verify_referenced_files():
    must = ["results/live_lang_thinking.jsonl", "results/thinking_sweep.jsonl",
            "results/stats_thinking.txt", "results/sweep_summary.txt",
            "data/sentence_pairs.json", "lab/pricing.py"]
    for f in must:
        check(f"참조 파일 존재: {f}", os.path.exists(os.path.join(ROOT, f)))
    # 없는 것이 정상이지만 각주에서 안내하면 안 되는 파일
    absent = os.path.join(ROOT, "results/live_lang.jsonl")
    check("슬라이드6 N=100 원자료 부재를 문서가 인정하는가",
          (not os.path.exists(absent)) and
          ("패키지에 포함되어 있지 않" in open(
              os.path.join(ROOT, "LIVE_RESULTS.md"), encoding="utf-8").read()),
          "파일이 없으면 '재실행 필요'를 문서에 명시해야 한다", level="WARN")


# ────────────────────────────────────────────────────────────────
# 8. 덱 텍스트 직접 대조 (선택 — python-pptx 필요)
# ────────────────────────────────────────────────────────────────
BANNED = [
    ("답은 여섯 번 다 같은 숫자", "정답률이 아니라 문자열 동일을 주장 — 원자료와 불일치"),
    ("같은 1,000 토큰이라도", "단위 10배 오류 (10,000 토큰이어야 함)"),
    ("exp01~exp07", "exp09·tools 누락된 구버전 표기"),
    ("$37.32  ← 오답", "6회 중 1회만 표기 — 실제 4회 오답"),
]


def verify_pptx(path):
    try:
        from pptx import Presentation
    except ImportError:
        check("덱 텍스트 대조", False, "python-pptx 없음 — pip install python-pptx", level="SKIP")
        return
    if not os.path.exists(path):
        check("덱 텍스트 대조", False,
              f"{os.path.basename(path)} 없음 — 저장소 단독 사용 시 정상 "
              f"(덱은 발표 패키지에 있음)", level="SKIP")
        return
    prs = Presentation(path)
    texts = []
    for s in prs.slides:
        for sh in s.shapes:
            if sh.has_text_frame:
                texts.append(sh.text_frame.text)
    blob = "\n".join(texts)
    n = len(prs.slides._sldIdLst)
    check("덱 29장 (본편 28 + QnA/리포 1)", n == 29, f"실제 {n}장")
    check("덱에 깨진 문자(U+FFFD) 없음", "\ufffd" not in blob)
    for phrase, why in BANNED:
        check(f"덱에 수정 전 문구 없음: '{phrase[:28]}'", phrase not in blob, why)
    # 정답률 표기가 실제로 들어갔는지
    check("덱 슬라이드25에 정답률 표기 존재", "정답 6/6" in blob and "정답 2/6" in blob,
          "응답 문자열 대신 정답률(n/6)로 바뀌어 있어야 한다")
    check("덱 슬라이드5 6번째 행 존재", "에러 분석 문장" in blob,
          "합계가 6문장인데 5행만 그려져 있으면 암산으로 걸린다")
    check("덱 마지막 장 = QnA + 리포 안내", "질문 받겠습니다" in blob
          and "token-cost-lab — 무엇이 들어 있나" in blob)
    check("덱에 리포 주소 표기", "giyeop-cody/token-cost-lab" in blob)
    # QR 이미지가 실제로 박혀 있는가 (마지막 슬라이드)
    last = list(prs.slides)[-1]
    pics = [sh for sh in last.shapes if sh.shape_type == 13]
    check("덱 마지막 장에 QR 이미지 존재", len(pics) >= 1,
          f"이미지 {len(pics)}개")


# ────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--pptx", default=find_deck())
    args = ap.parse_args()

    print("=" * 78)
    print("  verify_deck.py — 슬라이드 수치 회귀 검사")
    print("=" * 78)

    verify_referenced_files()
    verify_slide7()
    verify_slide25()
    verify_tables()
    verify_caching_consistency()
    verify_units()
    verify_agent_loop()
    verify_pptx(args.pptx)

    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    skips = [r for r in results if r[0] == "SKIP"]
    passes = [r for r in results if r[0] == "PASS"]

    if args.verbose:
        for lvl, name, ok, detail in results:
            if lvl == "PASS":
                print(f"  \033[32m✓\033[0m {name}")
    for lvl, name, ok, detail in results:
        if lvl == "SKIP":
            print(f"  \033[90m–\033[0m {name}  ({detail})")
    for lvl, name, ok, detail in results:
        if lvl == "WARN":
            print(f"  \033[33m!\033[0m {name}\n      {detail}")
    for lvl, name, ok, detail in results:
        if lvl == "FAIL":
            print(f"  \033[31m✗\033[0m {name}\n      {detail}")

    print("-" * 78)
    print(f"  통과 {len(passes)} · 경고 {len(warns)} · 건너뜀 {len(skips)} · "
          f"실패 {len(fails)}")
    if fails:
        print("  \033[31m원자료와 슬라이드가 어긋납니다. 덱을 고치거나 수치를 갱신하세요.\033[0m")
    elif skips:
        print("  \033[33m실패는 없지만 건너뛴 검사가 있습니다 — "
              "의존성을 설치하고 다시 돌리세요.\033[0m")
    else:
        print("  \033[32m슬라이드의 모든 수치가 원자료와 일치합니다.\033[0m")
    print("=" * 78)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
