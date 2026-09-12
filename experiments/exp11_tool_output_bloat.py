# -*- coding: utf-8 -*-
"""
실험 11 — 툴 출력의 컨텍스트 팽창 (코딩 에이전트)

무엇을 재는가:
  코딩 에이전트에서 툴(파일 읽기 · 테스트 실행 · 에러 로그)이 반환한 입력 토큰은
  **일회성이 아니다.** 컨텍스트에 머물러 매 턴 재전송되고 매번 다시 과금된다.
  이 실험은 그 크기를 정량화한다.

  A. 시뮬레이션 (무료 · 키 불필요)
     툴이 매 턴 K 토큰을 반환할 때 N턴 루프의 총 입력 토큰과 비용을,
     세 가지 전략으로 비교한다:
       1) naive     — 툴 출력이 전부 컨텍스트에 누적
       2) compact   — 10턴마다 이력을 1,500 토큰 요약으로 접기
       3) subagent  — 탐색은 서브에이전트가 하고 메인에 1,500 톰 요약만 반환
  B. 라이브 실측 (GEMINI_API_KEY 필요 · 과금)
     Gemini function calling으로 실제 read_file 툴을 2턴 돌려
     usageMetadata 의 toolUsePromptTokenCount 와 promptTokenCount 증가를 읽는다.

왜 중요한가:
  exp04 가 "루프는 2차 함수"를 보여준다면, 이 실험은 매 턴 증분에서
  **툴 출량이 차지하는몫**을 분리해 보인다. SOURCES.md §2.3 에
  toolUsePromptTokenCount 필드가 소개되어 있지만 실측 실험은 없었 —
  이 실험이 그 실측이다.

주의 (정직하게):
  * A는 tiktoken 실측(툴 출력 실문장 인코딩) + lab/pricing.py 단가의 시뮬레이션.
  * B는 실제 호출의 usageMetadata 다. 단, 세션 1회 — 여러 번 돌려 확인하라.
  * 툴 출력 K 토큰은 --tool-tokens 로 조정할 수 있다. 자기 에이전트의
    실제 툴 응답 크기를 넣고 돌리는 것이 목적이다.

실행:
  python experiments/exp11_tool_output_bloat.py                 # A만 (무료)
  python experiments/exp11_tool_output_bloat.py --turns 40 --tool-tokens 20000
  python experiments/exp11_tool_output_bloat.py --live          # A+B (B는 과금)

출처:
  Gemini API — Function calling
    https://ai.google.dev/gemini-api/docs/function-calling
  GenerateContentResponse.UsageMetadata (toolUsePromptTokenCount 필드)
    https://ai.google.dev/api/generate-content#UsageMetadata
  Anthropic — Effective context engineering for AI agents (2025-09)
    https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
    (서브에이전트는 수만 토큰을 탐색해도 1,000~2,000 토큰 요약만 반환)
  저장소 내 대조: experiments/exp04_agent_loop_sdd.py
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

# ───────────────────────────────────────────────── A. 시뮬레이션

# 합성 코드 파일 — read_file 툴이 실제로 반환할 모양의 텍스트
SYNTH_FILE = "\n".join(
    f"def handler_{i:03d}(payload):  # service={i % 7}"
    f" -> validate payload, apply rule {i}, persist and return"
    for i in range(400)
)


def synth_tokens(enc) -> int:
    return len(enc.encode(SYNTH_FILE))


def sim_loop(turns: int, tool_tok: int, base: int, agent_out: int,
             strategy: str, every: int = 10, summary: int = 1500) -> int:
    """턴별 입력 토큰 합. strategy ∈ {naive, compact, subagent}."""
    total = 0
    history = base
    for t in range(turns):
        total += history                      # 이 턴에 전송하는 컨텍스트
        if strategy == "subagent":
            # 탐색은 서브에이전트에서: 메인 컨텍스트에는 요약만 한 번
            if t == 0:
                history += summary + agent_out
            else:
                history += agent_out
        else:
            history += agent_out + tool_tok   # 툴 출력이 컨텍스트에 남는다
            if strategy == "compact" and t > 0 and t % every == every - 1:
                history = base + summary      # 이력을 요약으로 접음
    return total


def mode_sim(args, m: pricing.Model):
    enc = _encoding()
    k = args.tool_tokens
    report.section("A. 시뮬레이션 — 매 턴 툴이 K 토큰을 반환할 때")
    if enc is not None:
        print(f"  참고: 합성 파일(400줄)의 tiktoken 실측치 = {synth_tokens(enc):,} tok")
    else:
        print(f"  ⚠️ tiktoken 을 구할 수 없어 --tool-tokens={k:,} 을 그대로 사용.")
    print(f"  전제: 초기 컨텍스트 {args.base:,} tok · 에이전트 출력/턴 {args.agent_out:,} tok")
    print(f"        툴 출력 K = {k:,} tok · 턴 수 = {args.turns} · {m.name} 단가\n")

    strategies = ("naive", "compact", "subagent")
    measured = {}
    for name in strategies:
        inp_tok = sim_loop(args.turns, k, args.base, args.agent_out, name)
        measured[name] = (inp_tok,
                          pricing.cost(m, inp_tok, args.turns * args.agent_out))
    naive_cost = measured["naive"][1]
    rows = []
    for name in strategies:
        inp_tok, cost = measured[name]
        delta = "기준" if name == "naive" else f"−{(1 - cost / naive_cost) * 100:.0f}%"
        rows.append([name, f"{inp_tok:,}", pricing.usd(cost, 2), delta])

    report.table(["전략", f"{args.turns}턴 총 입력", f"총 비용 ({m.name})", "naive 대비"],
                 rows, ["l", "r", "r", "r"])
    print(f"""
  → 툴 출력 {k:,} tok 은 {args.turns}턴 동안 **{k * args.turns:,} tok** 에
    다시 과금된다. 툴 응답이 클수록, 세션이 길수록 차이가 벌어진다.
  → subagent 는 탐색을 메인 컨텍스트 밖으로 내보내는 것 — Anthropic 이
    권장하는 방식(수만 토큰 탐색 → 1~2K 요약 반환)과 동일 구조.
  ※ naive/compact/subagent 모두 토큰 수만 비교한다. 품질 차이는 측정하지 않는다.""")


# ───────────────────────────────────────────────── B. 라이브 실측

def _post(url: str, payload: dict, key: str) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"\n  API 오류 {e.code}\n  {body}\n")
    except urllib.error.URLError as e:
        raise SystemExit(f"\n  네트워크 오류: {e.reason}\n")


TOOL = {"functionDeclarations": [{
    "name": "read_file",
    "description": "Read a text file and return its content.",
    "parameters": {"type": "object",
                   "properties": {"path": {"type": "string"}},
                   "required": ["path"]},
}]}

SYSTEM = ("You are a coding agent. Use the read_file tool when asked about a "
          "file's content. Keep final answers to one sentence.")


def mode_live(args, m: pricing.Model, key: str):
    report.section(f"B. 라이브 실측 — function calling 2턴  ·  model={args.api_model}")
    print(f"  단가 기준: {m.name} · 실제 과금됩니다.\n")
    url = (f"https://generativelanguage.googleapis.com/v1beta/"
           f"models/{args.api_model}:generateContent")

    contents = [
        {"role": "user", "content": {"parts": [{"text": SYSTEM}]}},
        {"role": "user", "content": {"parts":
            [{"text": "docs/service.py 파일을 읽어서 첫 3개 함수 이름을 알려줘."}]}},
    ]
    payload = {"contents": contents, "tools": [TOOL],
               "generationConfig": {"maxOutputTokens": 400}}

    # ── 턴 1: 모델이 read_file(functionCall) 을 요청할 것
    print("  [턴1] 호출 중 (functionCall 기대)...", flush=True)
    r1 = _post(url, payload, key)
    parts1 = (r1.get("candidates", [{}])[0]
              .get("content", {}) or {}).get("parts", []) or []
    fc = next((p.get("functionCall") for p in parts1
               if "functionCall" in p), None)
    if fc is None:
        raise SystemExit("\n  턴1: functionCall 이 돌아오지 않아 B 모드를 종료합니다.\n"
                         "  응답: " + json.dumps(r1.get("candidates", []))[:300] + "\n")
    u1 = r1.get("usageMetadata", {}) or {}
    print(f"  [턴1] {fc['name']} 요청 확인. 툴을 실행합니다 "
          f"({len(SYNTH_FILE):,}자 합성 파일 반환)\n")

    # ── 턴 2: functionResponse(장문) + 재질문
    contents = contents + [
        {"role": "model", "content": {"parts":
            [{"functionCall": {"name": fc["name"], "args": fc.get("args", {})}}]}},
        {"role": "user", "content": {"parts":
            [{"functionResponse": {"name": fc["name"],
                                   "response": {"content": SYNTH_FILE}}}]}},
        {"role": "user", "content": {"parts":
            [{"text": "지금까지 본 내용을 한 문장으로 요약해 줘."}]}},
    ]
    payload = {"contents": contents, "tools": [TOOL],
               "generationConfig": {"maxOutputTokens": 400}}

    print("  [턴2] 호출 중 (장문 컨텍스트 재전송)...", flush=True)
    t0 = time.time()
    r2 = _post(url, payload, key)
    u2 = r2.get("usageMetadata", {}) or {}
    text2 = "".join(p.get("text", "") for c in r2.get("candidates", [])
                    for p in (c.get("content", {}) or {}).get("parts", []) or [])
    print(f"  [턴2] 완료 ({time.time() - t0:.1f}초)\n")

    def bill(u):
        prompt = int(u.get("promptTokenCount", 0) or 0)
        cached = int(u.get("cachedContentTokenCount", 0) or 0)
        tools = int(u.get("toolUsePromptTokenCount", 0) or 0)
        out = (int(u.get("candidatesTokenCount", 0) or 0)
               + int(u.get("thoughtsTokenCount", 0) or 0))
        return prompt, cached, tools, out

    p1, c1, t1, o1 = bill(u1)
    p2, c2, t2, o2 = bill(u2)
    rows = [
        ["턴1 (툴 호출 전)", f"{p1:,}", f"{c1:,}", f"{t1:,}", f"{o1:,}",
         pricing.usd(pricing.cost(m, p1 - c1 + t1, o1, cached_tok=c1), 6)],
        ["턴2 (장문 재전송)", f"{p2:,}", f"{c2:,}", f"{t2:,}", f"{o2:,}",
         pricing.usd(pricing.cost(m, p2 - c2 + t2, o2, cached_tok=c2), 6)],
    ]
    report.table(["턴", "prompt", "캐시", "toolUse", "출력계", "비용"],
                 rows, ["l", "r", "r", "r", "r", "r"])

    growth = p2 - p1
    print(f"""
  → 턴2 의 promptTokenCount 는 {p1:,} → {p2:,} ({growth:+,}) 으로 늘었다.
    증가분의 대부분은 턴1에 반환된 {len(SYNTH_FILE):,}자 파일 내용이다 —
    **이미 한 번 과금한 툴 출력이 다시 과금된 것**이다.
  → toolUsePromptTokenCount = {t2:,}: 함수 호출·실행이 내부적으로 소비한
    입력 토큰도 별도 필드로 실재한다 (SOURCES.md §2.3).
  → 실무 함의: 툴 응답을 절단하거나 요약해서 주입하면 이 재과금이 줄어든다.
    subagent(요약 반환)가 효과적인 이유가 여기서 나온다.
  ※ 세션 1회 결과다. 안정성 확인을 위해 여러 번 돌려야 한다.""")
    print("\n  턴2 응답: " + text2.strip()[:200])


# ───────────────────────────────────────────────── 공통

def _encoding():
    try:
        import tiktoken
        return tiktoken.get_encoding("o200k_base")
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(
        description="툴 출력의 컨텍스트 팽창 (코딩 에이전트)")
    ap.add_argument("--model", default="sonnet",
                    help="lab/pricing.py 단가 키 (시뮬레이션)")
    ap.add_argument("--turns", type=int, default=20)
    ap.add_argument("--tool-tokens", type=int, default=8000,
                    help="매 턴 툴이 반환하는 토큰 K (자기 에이전트 실측치로)")
    ap.add_argument("--base", type=int, default=5000,
                    help="초기 컨텍스트 (시스템 프롬프트+툴 스키마)")
    ap.add_argument("--agent-out", type=int, default=300,
                    help="턴당 에이전트 출력 토큰")
    ap.add_argument("--live", action="store_true",
                    help="B 라이브 실측 (GEMINI_API_KEY 필요 · 과금)")
    ap.add_argument("--api-model", default="gemini-3.7-flash",
                    help="B 모드 API 모델명 (기본: gemini-3.7-flash). "
                         "가용 목록은 exp08 --list-models 로 확인.")
    args = ap.parse_args()

    report.title("실험 11 — 툴 출력의 컨텍스트 팽창 (코딩 에이전트)")
    m = pricing.get(args.model)

    mode_sim(args, m)

    if args.live:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            print("\n  [건너뜀] B 라이브 실측은 GEMINI_API_KEY 가 필요합니다.\n")
        else:
            mode_live(args, m, key)


if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
