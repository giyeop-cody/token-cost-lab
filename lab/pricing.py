# -*- coding: utf-8 -*-
"""
단가 테이블 (USD / 1M tokens). 가격 스냅샷과 과거 환산 시나리오를 분리한다.

⚠️ 가격은 수시로 바뀝니다. 발표/보고 전에 반드시 벤더 공식 페이지에서 재확인하고
   아래 값을 갱신하세요. 라이브 비용은 API 모델 ID에 매핑한다. 종량 단가 환산이며 실제 청구서가 아니다.
   캐시 저장료·도구 사용료·세금·구독료·장문 할증은 별도다.

2026-09-11 추가: Gemini 3.5~3.8 Flash · Claude Haiku 4.5
  출처: https://ai.google.dev/gemini-api/docs/pricing · https://www.anthropic.com/pricing
  ⚠️ Gemini 3.6/3.7/3.8 Flash의 $0.75/$3.75는 **2026-12-31까지 introductory 가격**이며
     2027-01-01부터 $1.50/$7.50으로 2배 오른다. 3.5 Flash($1.50/$9.00)는 상시 가격.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    name: str
    inp: float           # 입력 $/1M
    out: float           # 출력 $/1M
    cache_read: float    # 캐시 읽기 배수 (입력 단가 대비)
    cache_write: float   # 캐시 쓰기 배수 (입력 단가 대비)
    batch: float = 0.5   # 지원되는 Batch 시나리오의 입력·출력 배수
    cache_min_tokens: int | None = None  # None이면 적격성 미확인, 할인 가정 금지
    api_id: str | None = None
    source: str = ""
    verified_on: str = ""
    basis: str = "Standard text / short-context snapshot"

    def __post_init__(self):
        if self.verified_on and not self.source:
            raise ValueError("verification date requires a source; scenarios are not verified prices")

    @property
    def ratio(self) -> float:
        """출력 단가 / 입력 단가."""
        return self.out / self.inp


GOOGLE_PRICING = "https://ai.google.dev/gemini-api/docs/pricing"
CLAUDE_PRICING = "https://platform.claude.com/docs/en/build-with-claude/prompt-caching"

MODELS = {
    "opus":        Model("Claude Opus 4.6",  5.00, 25.00, 0.10, 1.25, cache_min_tokens=4096, api_id="claude-opus-4-6", source=CLAUDE_PRICING, verified_on="2026-09-20"),
    "sonnet":      Model("Claude Sonnet 4.6", 3.00, 15.00, 0.10, 1.25, cache_min_tokens=1024, api_id="claude-sonnet-4-6", source=CLAUDE_PRICING, verified_on="2026-09-20"),
    "gpt5":        Model("GPT-5", 1.25, 10.00, 0.10, 1.00, cache_min_tokens=1024, api_id="gpt-5", source="https://developers.openai.com/api/docs/pricing", verified_on="2026-09-20"),
    "gemini-pro":  Model("Gemini 3.1 Pro Preview (≤200k)", 2.00, 12.00, 0.10, 1.00, cache_min_tokens=4096, api_id="gemini-3.1-pro-preview", source=GOOGLE_PRICING, verified_on="2026-09-20"),
    "gemini-25":   Model("Gemini 2.5 Pro (≤200k)", 1.25, 10.00, 0.10, 1.00, cache_min_tokens=2048, api_id="gemini-2.5-pro", source=GOOGLE_PRICING, verified_on="2026-09-20"),
    "deepseek":    Model("DeepSeek V4.1 Flash (peak)", 0.30, 1.20, 0.02, 1.00, batch=1.0, api_id="deepseek-flash", source="https://api-docs.deepseek.com/quick_start/pricing", basis="peak rates; off-peak is half", verified_on="2026-09-20"),
    "deepseek-offpeak": Model("DeepSeek V4.1 Flash (off-peak)", 0.15, 0.60, 0.02, 1.00, batch=1.0, source="https://api-docs.deepseek.com/quick_start/pricing", basis="off-peak snapshot", verified_on="2026-09-20"),
    # 라이브 실측(exp08·tools/*)에서 실제로 호출한 모델.
    # 현행 LIVE_RESULTS는 실제 모델 Standard와 LEGACY_TALK 환산을 병기한다.
    # 과거 환산은 실제 Flash-Lite 역사 가격이라는 뜻이 아니다.
    "flash-lite":  Model("Gemini 3.1 Flash-Lite", 0.25, 1.50, 0.10, 1.00, cache_min_tokens=None, api_id="gemini-3.1-flash-lite", source=GOOGLE_PRICING, verified_on="2026-09-20"),

    # ── 2026-09-11 추가 (벤더 공식 가격 페이지 확인) ──────────────────
    # Google: context caching = 입력 단가의 10% (90% 할인), 쓰기 프리미엄 없음
    #         (캐시 저장료는 별도 시간당 과금 — 본 테이블엔 미포함).
    # ⚠️ 3.6/3.7/3.8 Flash는 2026-12-31까지 introductory, 2027년부터 2배.
    "gemini-35f":  Model("Gemini 3.5 Flash",  1.50,  9.00, 0.10, 1.00, cache_min_tokens=4096, api_id="gemini-3.5-flash", source=GOOGLE_PRICING, verified_on="2026-09-20"),
    "gemini-36f":  Model("Gemini 3.6 Flash",  0.75,  3.75, 0.10, 1.00, cache_min_tokens=4096, api_id="gemini-3.6-flash", source=GOOGLE_PRICING, verified_on="2026-09-20"),
    "gemini-37f":  Model("Gemini 3.7 Flash",  0.75,  3.75, 0.10, 1.00, cache_min_tokens=4096, api_id="gemini-3.7-flash", source=GOOGLE_PRICING, verified_on="2026-09-20"),
    "gemini-38f":  Model("Gemini 3.8 Flash",  0.75,  3.75, 0.10, 1.00, cache_min_tokens=4096, api_id="gemini-3.8-flash", source=GOOGLE_PRICING, verified_on="2026-09-20"),
    # Anthropic: cache read 0.1×, cache write 1.25× (5분 TTL).
    "haiku":       Model("Claude Haiku 4.5", 1.00, 5.00, 0.10, 1.25, cache_min_tokens=4096, api_id="claude-haiku-4-5", source=CLAUDE_PRICING, verified_on="2026-09-20"),
}

# Preserve the talk's arithmetic; never label this Flash-Lite's historical official rate.
LEGACY_TALK = Model("legacy talk conversion ($1.25/$10)", 1.25, 10.0, 0.25, 1.0,
                    verified_on="", basis="historical presentation assumption, not model price")
TIER_SCENARIOS = {"small": (0.15, 0.60), "mid": (1.25, 10.00),
                  "large": (5.00, 30.00), "web": (0.0, 0.0), "batch": (0.625, 5.00)}
DEFAULT = "sonnet"


def for_api(model_id: str) -> Model:
    matches = [m for m in MODELS.values() if m.api_id == model_id]
    if len(matches) != 1:
        raise ValueError(f"Unmapped API model {model_id!r}; supply an explicit price model, do not silently use another model's rate")
    return matches[0]


def cache_eligible(model: Model, prefix_tokens: int) -> bool:
    return model.cache_min_tokens is not None and prefix_tokens >= model.cache_min_tokens


def log_cost(row: dict, basis: str = "actual") -> float:
    if basis not in {"actual", "legacy"}:
        raise ValueError("unknown price basis")
    m = LEGACY_TALK if basis == "legacy" else for_api(row["model"])
    return cost(m, row["prompt"], row["thoughts"] + row["cands"], row.get("cached", 0))


def gemini_usage_cost(model: Model, usage: dict) -> float:
    # promptTokenCount INCLUDES cachedContentTokenCount. Subtract only in cost().
    # toolUsePromptTokenCount is reported separately, not assumed billable without
    # a documented per-model billing rule. It is not the local function response size.
    return cost(model, int(usage.get("promptTokenCount", 0) or 0),
                int(usage.get("candidatesTokenCount", 0) or 0) + int(usage.get("thoughtsTokenCount", 0) or 0),
                int(usage.get("cachedContentTokenCount", 0) or 0))


def get(key: str = DEFAULT) -> Model:
    if key not in MODELS:
        raise SystemExit(
            f"알 수 없는 모델 '{key}'. 사용 가능: {', '.join(MODELS)}"
        )
    return MODELS[key]


def cost(model: Model, inp_tok: int, out_tok: int,
         cached_tok: int = 0, batch: bool = False) -> float:
    """USD 비용. cached_tok 은 inp_tok 중 캐시 읽기로 처리되는 부분."""
    if min(inp_tok, out_tok, cached_tok) < 0 or cached_tok > inp_tok:
        raise ValueError("token counts must be nonnegative; cached_tok is a subset of inp_tok")
    fresh = inp_tok - cached_tok
    usd = (fresh * model.inp
           + cached_tok * model.inp * model.cache_read
           + out_tok * model.out) / 1e6
    return usd * (model.batch if batch else 1.0)


def usd(x: float, digits: int = 4) -> str:
    return f"${x:,.{digits}f}"
