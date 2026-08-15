# -*- coding: utf-8 -*-
"""
실험 08 — Gemini 실시간 토큰 사용량 측정 (라이브 시연용)

무엇을 재는가:
  실제 Gemini API를 호출해서 usageMetadata 에 찍힌 **진짜 토큰 수**를 읽는다.
  시뮬레이션이 아니라 실제로 과금되는 값이다.

  A. countTokens  — 호출 전에 입력 토큰만 미리 센다 (무료, 과금 없음)
  B. generate     — 실제 생성 후 입력/출력/사고/캐시 토큰을 모두 본다

핵심 관전 포인트:
  1) 같은 질문을 한국어 / 영어로 던졌을 때 입력·출력 토큰 차이
  2) thoughtsTokenCount — 사고 토큰은 출력 단가로 과금된다 (덱의 핵심 주장)
  3) thinking_budget 을 낮추면 사고 토큰이 실제로 줄어드는가

준비:
  export GEMINI_API_KEY="..."      # https://aistudio.google.com/apikey 에서 발급
  pip install requests

실행:
  python experiments/exp08_gemini_live.py --count-only     # 과금 없이 입력 토큰만
  python experiments/exp08_gemini_live.py                  # 한/영 비교 실호출
  python experiments/exp08_gemini_live.py --thinking       # 사고 예산 비교
  python experiments/exp08_gemini_live.py --prompt "..."   # 내 프롬프트로
  python experiments/exp08_gemini_live.py --model gemini-2.5-flash

주의:
  --count-only 를 제외한 모든 모드는 **실제로 과금**됩니다.
  기본 프롬프트는 매우 짧아 통상 1센트 미만이지만, 요금을 인지하고 실행하세요.

계측 시 틀리기 쉬운 점:
  1) promptTokenCount 는 캐시 토큰을 이미 포함한다.
     실제 과금 입력 = promptTokenCount - cachedContentTokenCount.
  2) 스트리밍에서 usageMetadata 는 청크마다 누적값으로 온다.
     합산하지 말고 마지막 청크 값만 쓸 것.
  3) 일부 SDK는 cachedContentTokenCount 를 0이 아닌 undefined 로 준다.

출처:
  Gemini API — Understanding and counting tokens
    https://ai.google.dev/gemini-api/docs/tokens
  GenerateContentResponse.UsageMetadata 필드 레퍼런스
    https://ai.google.dev/api/generate-content#UsageMetadata
  Gemini thinking (사고 토큰은 출력 단가로 과금)
    https://ai.google.dev/gemini-api/docs/thinking
  가격 — https://ai.google.dev/pricing   (단가 테이블: lab/pricing.py)
  전체 목록: ../SOURCES.md
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab import pricing, report  # noqa: E402

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"

# 같은 의미의 한/영 질문 쌍 — 사고를 유발하되 답이 짧은 과제
PAIR = {
    "en": "A cache holds 20,000 tokens. Cached reads cost 25% of the input rate. "
          "If the input rate is $2 per million tokens, how much do 100 cached reads cost? "
          "Answer with the number only.",
    "ko": "캐시에 20,000 토큰이 저장되어 있습니다. 캐시 읽기는 입력 단가의 25%로 과금됩니다. "
          "입력 단가가 100만 토큰당 2달러일 때, 캐시 읽기 100회의 비용은 얼마입니까? "
          "숫자만 답하세요.",
}

# usageMetadata 필드 → 사람이 읽는 이름
FIELDS = [
    ("promptTokenCount",       "입력 (prompt)"),
    ("cachedContentTokenCount", "  └ 캐시 히트분"),
    ("thoughtsTokenCount",     "사고 (thinking)"),
    ("candidatesTokenCount",   "출력 (candidates)"),
    ("toolUsePromptTokenCount", "도구 사용 입력"),
    ("totalTokenCount",        "합계"),
]


def _key() -> str:
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not k:
        raise SystemExit(
            "\n  GEMINI_API_KEY 가 없습니다.\n"
            "  1) https://aistudio.google.com/apikey 에서 키를 발급받으세요 (무료 등급 있음).\n"
            "  2) export GEMINI_API_KEY=\"발급받은키\"\n"
            "  3) 다시 실행하세요.\n\n"
            "  키 없이 구조만 보려면:  python experiments/exp08_gemini_live.py --dry-run\n"
        )
    return k


def _post(url: str, payload: dict, key: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise SystemExit(f"\n  API 오류 {e.code}\n  {body}\n")
    except urllib.error.URLError as e:
        raise SystemExit(f"\n  네트워크 오류: {e.reason}\n")


def count_tokens(model: str, text: str, key: str) -> int:
    """호출 전 입력 토큰만 계산한다. 과금되지 않는다."""
    url = f"{API_ROOT}/{model}:countTokens"
    payload = {"contents": [{"parts": [{"text": text}]}]}
    return int(_post(url, payload, key).get("totalTokens", 0))


def generate(model: str, text: str, key: str,
             thinking_budget=None, max_out: int = 400) -> dict:
    """실제 생성. usageMetadata 와 응답 텍스트를 돌려준다."""
    url = f"{API_ROOT}/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {"maxOutputTokens": max_out},
    }
    if thinking_budget is not None:
        payload["generationConfig"]["thinkingConfig"] = {
            "thinkingBudget": int(thinking_budget)
        }

    t0 = time.time()
    data = _post(url, payload, key)
    elapsed = time.time() - t0

    usage = data.get("usageMetadata", {}) or {}
    out_text = ""
    for cand in data.get("candidates", []):
        for part in (cand.get("content", {}) or {}).get("parts", []) or []:
            if "text" in part:
                out_text += part["text"]

    return {"usage": usage, "text": out_text.strip(), "elapsed": elapsed}


def _billable(usage: dict) -> tuple:
    """(과금 입력, 캐시 입력, 과금 출력) — 출력에는 사고 토큰이 포함된다."""
    prompt = int(usage.get("promptTokenCount", 0) or 0)
    cached = int(usage.get("cachedContentTokenCount", 0) or 0)
    thoughts = int(usage.get("thoughtsTokenCount", 0) or 0)
    cands = int(usage.get("candidatesTokenCount", 0) or 0)
    tools = int(usage.get("toolUsePromptTokenCount", 0) or 0)
    fresh_in = max(prompt - cached, 0) + tools
    out = cands + thoughts          # ★ 사고 토큰도 출력 단가로 과금
    return fresh_in, cached, out


def show_usage(usage: dict) -> None:
    rows = []
    for f, label in FIELDS:
        v = usage.get(f)
        if v is None and f in ("cachedContentTokenCount", "thoughtsTokenCount",
                               "toolUsePromptTokenCount"):
            v = 0
        if v is None:
            continue
        rows.append([label, f"{int(v):,}"])
    report.table(["usageMetadata 필드", "토큰"], rows, ["l", "r"])


def price_it(usage: dict, m) -> float:
    fresh_in, cached, out = _billable(usage)
    return pricing.cost(m, fresh_in + cached, out, cached_tok=cached)


# ─────────────────────────────────────────────────────────── 모드

def mode_count_only(args, key):
    report.section("입력 토큰만 계산 (countTokens — 과금 없음)")
    print("  같은 의미의 질문을 영어/한국어로 각각 인코딩합니다.\n")

    en = count_tokens(args.model, PAIR["en"], key)
    ko = count_tokens(args.model, PAIR["ko"], key)
    ratio = ko / en if en else 0

    report.table(
        ["언어", "글자 수", "입력 토큰", "영어 대비"],
        [["영어", f"{len(PAIR['en']):,}", f"{en:,}", "1.00×"],
         ["한국어", f"{len(PAIR['ko']):,}", f"{ko:,}", f"{ratio:.2f}×"]],
        ["l", "r", "r", "r"],
    )
    print()
    report.kv("Gemini 실측 배수", f"{ratio:.2f}×", "(exp01 tiktoken 실측: 1.44×)")
    print("\n  → 벤더 토크나이저마다 배수가 다릅니다. 자기 모델로 재보는 것이 정답입니다.")


def mode_compare(args, key):
    m = pricing.get(args.price_model)
    report.section(f"한국어 vs 영어 실호출 비교  ·  model={args.model}")
    print(f"  단가 기준: {m.name}  (${m.inp}/1M 입력, ${m.out}/1M 출력)")
    print("  ※ 실제 과금됩니다.\n")

    results = {}
    for lang in ("en", "ko"):
        label = "영어" if lang == "en" else "한국어"
        print(f"  [{label}] 호출 중...", flush=True)
        r = generate(args.model, PAIR[lang], key, max_out=args.max_out)
        results[lang] = r
        print(f"  [{label}] 완료 ({r['elapsed']:.1f}초)\n")

    rows = []
    for lang in ("en", "ko"):
        u = results[lang]["usage"]
        fin, cch, out = _billable(u)
        c = price_it(u, m)
        rows.append([
            "영어" if lang == "en" else "한국어",
            f"{fin:,}", f"{int(u.get('thoughtsTokenCount', 0) or 0):,}",
            f"{int(u.get('candidatesTokenCount', 0) or 0):,}",
            f"{out:,}", pricing.usd(c, 6),
        ])

    report.table(
        ["언어", "입력", "사고", "응답", "출력계", "비용"],
        rows, ["l", "r", "r", "r", "r", "r"],
    )

    c_en = price_it(results["en"]["usage"], m)
    c_ko = price_it(results["ko"]["usage"], m)
    print()
    if c_en > 0:
        diff = (c_ko / c_en - 1) * 100
        report.kv("한국어 추가 비용", f"{diff:+.1f}%")
        report.kv("1,000회 환산 차액", pricing.usd((c_ko - c_en) * 1000, 2))

    for lang in ("en", "ko"):
        label = "영어" if lang == "en" else "한국어"
        report.section(f"{label} 응답 원문 + usageMetadata")
        txt = results[lang]["text"]
        print("  " + (txt[:300] + ("…" if len(txt) > 300 else "")).replace("\n", "\n  "))
        print()
        show_usage(results[lang]["usage"])

    print()
    report.verdict(
        "한국어 사고·응답은 영어보다 비싸다",
        f"실측 {(c_ko / c_en - 1) * 100:+.1f}%" if c_en else "측정 실패",
        "단, 1회 호출은 표본 1개입니다. 응답 길이가 매번 달라 배수가 흔들리므로 "
        "여러 번 돌려 평균으로 말하세요. tiktoken 실측(exp01)은 1.44×였습니다.",
    )


def mode_thinking(args, key):
    m = pricing.get(args.price_model)
    report.section(f"사고 예산(thinking budget) 비교  ·  model={args.model}")
    print("  같은 질문에 사고 예산만 바꿔 호출합니다.")
    print("  사고 토큰은 응답에 보이지 않지만 출력 단가로 과금됩니다.\n")

    prompt = args.prompt or PAIR["en"]
    budgets = [0, 512, -1]        # 0=사고끔, -1=모델 자동
    rows = []
    for b in budgets:
        name = {0: "사고 끔 (0)", -1: "자동 (-1)"}.get(b, f"제한 {b}")
        print(f"  [{name}] 호출 중...", flush=True)
        try:
            r = generate(args.model, prompt, key,
                         thinking_budget=b, max_out=args.max_out)
        except SystemExit as e:
            print(f"  [{name}] 지원되지 않음 — 건너뜁니다.\n")
            rows.append([name, "-", "-", "-", "미지원"])
            continue
        u = r["usage"]
        th = int(u.get("thoughtsTokenCount", 0) or 0)
        ca = int(u.get("candidatesTokenCount", 0) or 0)
        rows.append([name, f"{th:,}", f"{ca:,}", f"{th + ca:,}",
                     pricing.usd(price_it(u, m), 6)])
        print(f"  [{name}] 완료 ({r['elapsed']:.1f}초, 사고 {th:,}tok)\n")

    report.table(["사고 예산", "사고 tok", "응답 tok", "출력계", "비용"],
                 rows, ["l", "r", "r", "r", "r"])
    print("\n  → 사고 토큰이 출력계에 그대로 더해지는 것을 확인하세요.")
    print("     이것이 '추론 강도를 낮추라'는 원칙의 근거입니다.")


def mode_prompt(args, key):
    m = pricing.get(args.price_model)
    report.section("내 프롬프트 실측")
    pre = count_tokens(args.model, args.prompt, key)
    report.kv("호출 전 입력 토큰 (countTokens)", f"{pre:,}")

    if args.count_only:
        return

    print("\n  생성 호출 중...", flush=True)
    r = generate(args.model, args.prompt, key, max_out=args.max_out)
    print(f"  완료 ({r['elapsed']:.1f}초)\n")
    show_usage(r["usage"])
    print()
    report.kv("이번 호출 비용", pricing.usd(price_it(r["usage"], m), 6),
              f"({m.name} 단가 기준)")
    report.section("응답")
    print("  " + r["text"][:600].replace("\n", "\n  "))


def mode_list_models(args, key):
    """이 키로 실제 generateContent 가 가능한 모델만 추린다. 과금 없음."""
    import urllib.parse
    report.section("이 키로 사용 가능한 모델 (countTokens 로 검증 · 과금 없음)")
    url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200"
    req = urllib.request.Request(url, headers={"x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        listed = json.loads(r.read().decode()).get("models", [])

    rows = []
    for m in listed:
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        name = m["name"].replace("models/", "")
        if any(k in name for k in ("tts", "image", "robotics", "lyria", "video")):
            continue
        try:
            count_tokens(name, "ping", key)
            rows.append([name, "사용 가능", f"{m.get('inputTokenLimit', 0):,}"])
        except SystemExit:
            rows.append([name, "차단됨 (404)", "-"])

    report.table(["모델", "상태", "입력 한도"], rows, ["l", "l", "r"])
    print("\n  ※ gemini-2.5-* 계열은 신규 키에 더 이상 제공되지 않습니다.")
    print("     --model 로 '사용 가능' 표시된 모델을 지정하세요.")


def mode_dry_run(args):
    report.section("구조 미리보기 (--dry-run · API 호출 없음)")
    m = args.model
    print(f"""
  이 스크립트가 실제로 하는 일:

    1. POST {API_ROOT}/{m}:countTokens
       -> {{"totalTokens": 42}}                      ... 과금 없음

    2. POST {API_ROOT}/{m}:generateContent
       -> {{"candidates": [...],
            "usageMetadata": {{
               "promptTokenCount":        42,
               "thoughtsTokenCount":     517,   <- 출력 단가로 과금
               "candidatesTokenCount":    88,
               "cachedContentTokenCount":  0,
               "totalTokenCount":        647 }}}}

  과금 계산식 (lab/pricing.py 의 cost() 에 넣는 값):

    과금 입력 = promptTokenCount - cachedContentTokenCount + toolUsePromptTokenCount
    과금 출력 = candidatesTokenCount + thoughtsTokenCount
    비용     = 입력x입력단가 + 캐시x캐시단가 + 출력x출력단가

  ★ promptTokenCount 는 캐시 토큰을 이미 포함합니다.
    빼지 않으면 캐싱 절감분이 장부에 보이지 않습니다.

  ★ thoughtsTokenCount 는 응답 본문에 나타나지 않지만
    출력 단가로 과금됩니다. 덱의 핵심 주장이 바로 이 필드입니다.

  키를 설정하고 다시 실행하세요:

    export GEMINI_API_KEY="..."
    python experiments/exp08_gemini_live.py --count-only   # 과금 없음
    python experiments/exp08_gemini_live.py                # 한/영 실호출
    python experiments/exp08_gemini_live.py --thinking     # 사고 예산 비교
""")


def main():
    ap = argparse.ArgumentParser(
        description="Gemini 실시간 토큰 사용량 측정 (라이브 시연용)")
    ap.add_argument("--model", default="gemini-flash-latest",
                    help="Gemini 모델명 (기본: gemini-flash-latest). "
                         "gemini-2.5-* 는 신규 키에서 404 가 납니다 — "
                         "사용 가능 목록은 --list-models 로 확인하세요.")
    ap.add_argument("--price-model", default="gemini-25",
                    help="lab/pricing.py 의 단가 키 (기본: gemini-25)")
    ap.add_argument("--count-only", action="store_true",
                    help="countTokens 만 호출 — 과금 없음")
    ap.add_argument("--thinking", action="store_true",
                    help="사고 예산별 토큰 비교")
    ap.add_argument("--prompt", help="직접 지정한 프롬프트로 측정")
    ap.add_argument("--max-out", type=int, default=400, help="최대 출력 토큰")
    ap.add_argument("--dry-run", action="store_true",
                    help="API 호출 없이 동작 구조만 출력")
    ap.add_argument("--list-models", action="store_true",
                    help="이 키로 실제 호출 가능한 모델을 확인 (과금 없음)")
    args = ap.parse_args()

    report.title("실험 08 — Gemini 실시간 토큰 사용량 (실제 API)")

    if args.dry_run:
        mode_dry_run(args)
        return

    key = _key()

    if args.list_models:
        mode_list_models(args, key)
        return

    if args.prompt:
        mode_prompt(args, key)
    elif args.count_only:
        mode_count_only(args, key)
    elif args.thinking:
        mode_thinking(args, key)
    else:
        mode_compare(args, key)



if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
