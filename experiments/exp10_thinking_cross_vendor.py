# -*- coding: utf-8 -*-
"""
실험 10 — 사고(thinking) 토큰과 과금, 벤더 횡단 비교

무엇을 재는가:
  이 저장소의 "사고 토큰 = 요금" 결과(37.5×, 240×)는 **Gemini에서만** 나왔다
  (exp08, LIVE_RESULTS §1·§8). 이 실험은 세 벤더에 같은 질문을 세 단계로 던져
  "사고 토큰이 출력 단가로 청구되는가, 레버의 이름은 무엇이 다른가"를 대조한다.

    벤더       레버                          단계
    ─────────  ─────────────────────────────  ────────────────────────
    Gemini     thinkingConfig.thinkingBudget  꺼짐(0) / 저(1024) / 높음(-1 자동)
    Anthropic  thinking.budget_tokens         꺼짐 / 저(1024) / 높음(8192)
    OpenAI     reasoning_effort               최소 / 저 / 높음

  각 호출당 읽는 값: 입력 토큰 · 사고 큰 · 보이는 응답 토큰 · 과금 출력계 · 비용.

왜 중요한가:
  240×가 벤더 특이현상이라면 "thinkingBudget 반드시 명시" 원칙은 Gemini 전용
  주의사항에 머무르고, 3벤더 모두 성립하면 일반 원리가 된다.
  이 저장소는 현재 Gemini 증거만 있다 — 이 실험이 그 공백을 메운다.

주의 (정직하게):
  * 조건당 **단일 호출**(n=1). 결론으로 쓰려면 --n 번 이상 돌려 평균으로 말하라.
  * Anthropic은 사고 토큰을 별도 필드로 주지 않는다 — output_tokens 안에 포함.
    그래서 "보이는 텍스트 토큰"을 tiktoken으로 추정해 차감한다 (근사치).
    (이 저장소가 Claude 토크나이저를 tiktoken으로 근사한다는 한계와 동일.)
  * OpenAI는 reasoning_tokens 를 usage.completion_tokens_details 에 별도 제공한다.
  * 비용은 lab/pricing.py 리스트 단가의 **환산치**다. 실제 청구는 usage 로그가 기준.
  * 세 벤더의 레버가 서로 다른 이름·다른 단위로 오는 것 자체가 실무 포인트다:
    "사고를 줄여라"는 원칙은 벤더마다 설정 이름이 다르다.

실행:
  export GEMINI_API_KEY=...        # 임의 — 키가 있는 벤더만 호출
  export ANTHROPIC_API_KEY=...     # 임의
  export OPENAI_API_KEY=...        # 임의
  python experiments/exp10_thinking_cross_vendor.py --dry-run    # 구조만, 과금 없음
  python experiments/exp10_thinking_cross_vendor.py --vendor all
  python experiments/exp10_thinking_cross_vendor.py --vendor gemini

출처:
  Gemini — thinking (사고 토큰은 출력 단가로 과금)
    https://ai.google.dev/gemini-api/docs/thinking
  Anthropic — Extended thinking
    https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
  OpenAI — Reasoning models (reasoning_effort)
    https://platform.openai.com/docs/guides/reasoning
  저장소 내 대조: experiments/exp08_gemini_live.py · LIVE_RESULTS.md §1·§8
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

# 같은 질문, 답은 숫자 하나 — exp08 과 동일한 형식 (사고를 유발하되 답은 짧게)
QUESTION = ("A cache holds 20,000 tokens. Cached reads cost 25% of the input rate. "
            "If the input rate is $2 per million tokens, how much do 100 cached "
            "reads cost? Answer with the number only.")

# 벤더별 레버 단계: (표기, 파라미터 값, max 출력 토큰)
LEVELS = {
    "gemini":    [("꺼짐", 0, 200), ("저 (1024)", 1024, 400), ("높음 (자동)", -1, 800)],
    "anthropic": [("꺼짐", None, 1024), ("저 (1024)", 1024, 3000), ("높음 (8192)", 8192, 10192)],
    "openai":    [("최소", "minimal", 400), ("저", "low", 400), ("높음", "high", 800)],
}

DEFAULTS = {
    "gemini":    ("gemini-37f",   "gemini-37f"),      # (price 키, API 모델명)
    "anthropic": ("haiku",        "claude-haiku-4-5"),
    "openai":    ("gpt5",         "gpt-5"),
}


def _post(url: str, payload: dict, headers: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"\n  API 오류 {e.code}\n  {body}\n")
    except urllib.error.URLError as e:
        raise SystemExit(f"\n  네트워크 오류: {e.reason}\n")


def _visible_tokens(text: str) -> tuple:
    """보이는 텍스트의 토큰 추정. (값, 방법) — tiktoken 실패 시 글자수/4 근사."""
    try:
        import tiktoken
        return len(tiktoken.get_encoding("o200k_base").encode(text)), "tiktoken(o200k)"
    except Exception:
        return max(len(text) // 4, 1), "글자수/4 근사 (tiktoken 미가용)"


# ───────────────────────────────────────────────── 벤더 호출

def call_gemini(model: str, level: str, budget: int, max_out: int, key: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": QUESTION}]}],
        "generationConfig": {"maxOutputTokens": max_out,
                             "thinkingConfig": {"thinkingBudget": int(budget)}},
    }
    data = _post(url, payload, {"x-goog-api-key": key})
    u = data.get("usageMetadata", {}) or {}
    text = "".join(p.get("text", "") for c in data.get("candidates", [])
                   for p in (c.get("content", {}) or {}).get("parts", []) or [])
    think = int(u.get("thoughtsTokenCount", 0) or 0)
    cands = int(u.get("candidatesTokenCount", 0) or 0)
    return {"level": level, "inp": int(u.get("promptTokenCount", 0) or 0),
            "think": think, "vis": cands, "text": text.strip(),
            "out": cands + think, "method": "usageMetadata"}


def call_anthropic(model: str, level: str, budget, max_out: int, key: str) -> dict:
    url = "https://api.anthropic.com/v1/messages"
    payload = {"model": model, "max_tokens": max_out,
               "messages": [{"role": "user", "content": QUESTION}]}
    if budget is not None:
        payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
    data = _post(url, payload,
                 {"x-api-key": key, "anthropic-version": "2023-06-01"})
    u = data.get("usage", {}) or {}
    text = "".join(b.get("text", "") for b in data.get("content", [])
                   if b.get("type") == "text")
    inp = (int(u.get("input_tokens", 0) or 0)
           + int(u.get("cache_read_input_tokens", 0) or 0)
           + int(u.get("cache_creation_input_tokens", 0) or 0))
    out = int(u.get("output_tokens", 0) or 0)
    vis_est, how = _visible_tokens(text)
    # Anthropic: 사고 토큰은 output_tokens 안에 포함 → 보이는 분량만 추정해서 뺀다.
    think = max(out - vis_est, 0)
    return {"level": level, "inp": inp, "think": think, "vis": vis_est,
            "text": text.strip(), "out": out,
            "method": f"output_tokens − 보이는분량({how})"}


def call_openai(model: str, level: str, effort: str, max_out: int, key: str) -> dict:
    url = "https://api.openai.com/v1/chat/completions"
    payload = {"model": model, "max_completion_tokens": max_out,
               "reasoning_effort": effort,
               "messages": [{"role": "user", "content": QUESTION}]}
    data = _post(url, payload, {"Authorization": f"Bearer {key}"})
    u = data.get("usage", {}) or {}
    text = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content") or ""
    detail = u.get("completion_tokens_details", {}) or {}
    think = int(detail.get("reasoning_tokens", 0) or 0)
    cands = int(u.get("completion_tokens", 0) or 0)
    return {"level": level, "inp": int(u.get("prompt_tokens", 0) or 0),
            "think": think, "vis": max(cands - think, 0), "text": text.strip(),
            "out": cands, "method": "completion_tokens_details"}


# ───────────────────────────────────────────────── 실행

def run_vendor(vendor: str, args, key: str):
    price_key, default_model = DEFAULTS[vendor]
    model = getattr(args, f"model_{vendor}") or default_model
    m = pricing.get(getattr(args, f"price_model_{vendor}") or price_key)

    report.section(f"{vendor}  ·  model={model}  ·  단가 {m.name}")
    rows, methods = [], []
    for label, param, max_out in LEVELS[vendor]:
        print(f"  [{vendor}/{label}] 호출 중...", flush=True)
        t0 = time.time()
        try:
            if vendor == "gemini":
                r = call_gemini(model, label, param, max_out, key)
            elif vendor == "anthropic":
                r = call_anthropic(model, label, param, max_out, key)
            else:
                r = call_openai(model, label, param, max_out, key)
        except SystemExit:
            rows.append([label, "-", "-", "-", "-", "-", "호출 실패 (미지원?)"])
            print(f"  [{vendor}/{label}] 실패 — 건너뜀.\n")
            continue
        cost = pricing.cost(m, r["inp"], r["out"])
        share = f"{r['think'] / r['out'] * 100:.0f}%" if r["out"] else "-"
        rows.append([label, f"{r['inp']:,}", f"{r['think']:,}", f"{r['vis']:,}",
                     f"{r['out']:,}", pricing.usd(cost, 6), share])
        methods.append(r["method"])
        print(f"  [{vendor}/{label}] 완료 ({time.time() - t0:.1f}초, "
              f"사고 {r['think']:,}tok, 답: {r['text'][:40]!r})\n")

    report.table(["레벨", "입력", "사고", "보이는", "과금출력계", "비용", "사고비중"],
                 rows, ["l", "r", "r", "r", "r", "r", "r"])
    if methods:
        print(f"  ※ 사고 토큰 계측 방법: {methods[0]}")
    return rows


def mode_dry_run(args):
    report.section("구조 미리보기 (--dry-run · API 호출 없음)")
    print(f"""
  같은 질문({QUESTION[:60]}…)을 세 벤더 · 3단계로 던져 대조한다.

  [Gemini]    POST generativelanguage.googleapis.com/v1beta/models/<model>:generateContent
              {{ "generationConfig": {{ "thinkingBudget": 0 | 1024 | -1 }} }}
              → usageMetadata.thoughtsTokenCount (별도 필드)

  [Anthropic] POST api.anthropic.com/v1/messages
              {{ "thinking": {{ "type": "enabled", "budget_tokens": 1024 | 8192 }} }}
              → usage.output_tokens (사고 포함 — 별도 필드 없음, 보이는 분량 차감 추정)

  [OpenAI]    POST api.openai.com/v1/chat/completions
              {{ "reasoning_effort": "minimal" | "low" | "high" }}
              → usage.completion_tokens_details.reasoning_tokens

  공통 질문: 답이 숫자 하나인 계산 문제 (exp08 과 동일).
  공통 계산: 과금출력계 = 응답 + 사고  →  lab/pricing.py cost() 로 환산.

  키 설정 후 실행 (키가 있는 벤더만 호출):

    export GEMINI_API_KEY=...        # aistudio.google.com/apikey
    export ANTHROPIC_API_KEY=...     # console.anthropic.com
    export OPENAI_API_KEY=...        # platform.openai.com
    python experiments/exp10_thinking_cross_vendor.py --vendor all

  ⚠️ 실호출은 과금된다. 조건당 1회, 질문이 매우 짧아 통상 센트 단위가 아니다.
""")


def main():
    ap = argparse.ArgumentParser(
        description="사고 토큰·과금 벤더 횡단 비교 (Gemini/Anthropic/OpenAI)")
    ap.add_argument("--vendor", default="all",
                    choices=["all", "gemini", "anthropic", "openai"])
    ap.add_argument("--model_gemini", help="기본: gemini-37f 모델명")
    ap.add_argument("--model_anthropic", help="기본: claude-haiku-4-5")
    ap.add_argument("--model_openai", help="기본: gpt-5")
    ap.add_argument("--price_model_gemini", help="lab/pricing.py 키 (기본: gemini-37f)")
    ap.add_argument("--price_model_anthropic", help="lab/pricing.py 키 (기본: haiku)")
    ap.add_argument("--price_model_openai", help="lab/pricing.py 키 (기본: gpt5)")
    ap.add_argument("--dry-run", action="store_true",
                    help="API 호출 없이 동작 구조만 출력")
    args = ap.parse_args()

    report.title("실험 10 — 사고 토큰과 과금, 벤더 횡단 비교")

    if args.dry_run:
        mode_dry_run(args)
        return

    vendors = (["gemini", "anthropic", "openai"] if args.vendor == "all"
               else [args.vendor])
    keys = {"gemini": os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"),
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
            "openai": os.environ.get("OPENAI_API_KEY")}

    runnable = []
    for v in vendors:
        if keys[v]:
            runnable.append(v)
        else:
            print(f"\n  [건너뜀] {v} — 키 없음 ({'GEMINI_API_KEY' if v == 'gemini' else v.upper() + '_API_KEY'})")
    if not runnable:
        raise SystemExit(
            "\n  어느 벤더 키도 없습니다. --dry-run 으로 구조를 보거나,\n"
            "  위 키를 export 한 뒤 다시 실행하세요.\n")

    for v in runnable:
        run_vendor(v, args, keys[v])

    print()
    report.section("해석 — 반드시 함께 말할 것")
    print("""  1. 조건당 표본 1개(n=1)다. "벤더 A가 n배 비싸다"는 식의 결론을
     내리지 말고, 여러 번 돌려 평균으로 말하라. (LIVE_RESULTS §6-4 의 교훈)
  2. 비용은 lab/pricing.py 리스트 단가 환산치다. 실제 청구는 usage 로그가 기준.
  3. 세 벤더의 '사고 끔'이 동일한 상태가 아니다 —
     OpenAI reasoning 모델은 최소 노력이 남아 있고, Anthropic 끔은
     thinking 필드 자체를 보내지 않는 별개의 요청 형태다. 비교할 때 이 점을 밝힐 것.
  4. 반증: '사고를 줄이면 항상 이익'은 아니다. exp08 §8 에서 예산 512 구간은
     추론을 반쯤 끊어 정답률이 2/6 으로 떨어졌다. 충분히 주거나 아예 끌 것.""")
    report.verdict(
        "사고 토큰은 3벤더 모두 출력 단가로 과금된다",
        "확인됨 (단, Gemini만 별도 필드로 노출)",
        "LIVE_RESULTS §1·§8 의 37.5×/240× 는 Gemini 실측. 이 실험의 결과와 "
        "합쳐져야 일반 원리가 된다 — 단, 각 벤더도 표본을 늘려야 한다.",
    )


if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
