# -*- coding: utf-8 -*-
"""
단가 테이블 (USD / 1M tokens) — 2026-08 공개 리스트가 기준.

⚠️ 가격은 수시로 바뀝니다. 발표/보고 전에 반드시 벤더 공식 페이지에서 재확인하고
   아래 값을 갱신하세요. 이 파일이 이 저장소의 유일한 "가격 진실 공급원"입니다.

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
    batch: float = 0.5   # 배치 API 배수 (입력·출력 공통)

    @property
    def ratio(self) -> float:
        """출력 단가 / 입력 단가."""
        return self.out / self.inp


MODELS = {
    "opus":        Model("Claude Opus 4.6 / 5",  5.00, 25.00, 0.10, 1.25),
    "sonnet":      Model("Claude Sonnet 4.6",    3.00, 15.00, 0.10, 1.25),
    "gpt5":        Model("GPT-5.x (flagship)",   5.00, 30.00, 0.50, 1.00),
    "gemini-pro":  Model("Gemini 3.1 Pro",       2.00, 12.00, 0.25, 1.00),
    "gemini-25":   Model("Gemini 2.5 Pro",       1.25, 10.00, 0.25, 1.00),
    "deepseek":    Model("DeepSeek V4 Flash",    0.14,  0.28, 0.10, 1.00),
    # 라이브 실측(exp08·tools/*)에서 실제로 호출한 모델.
    # LIVE_RESULTS의 배수는 gemini-25 단가로 환산한 값이므로,
    # 실단가 기준 배수를 확인할 때 이 항목을 쓴다.
    "flash-lite":  Model("Gemini 3.1 Flash-Lite", 0.10,  0.40, 0.25, 1.00),

    # ── 2026-09-11 추가 (벤더 공식 가격 페이지 확인) ──────────────────
    # Google: context caching = 입력 단가의 10% (90% 할인), 쓰기 프리미엄 없음
    #         (캐시 저장료는 별도 시간당 과금 — 본 테이블엔 미포함).
    # ⚠️ 3.6/3.7/3.8 Flash는 2026-12-31까지 introductory, 2027년부터 2배.
    "gemini-35f":  Model("Gemini 3.5 Flash",  1.50,  9.00, 0.10, 1.00),
    "gemini-36f":  Model("Gemini 3.6 Flash",  0.75,  3.75, 0.10, 1.00),
    "gemini-37f":  Model("Gemini 3.7 Flash",  0.75,  3.75, 0.10, 1.00),
    "gemini-38f":  Model("Gemini 3.8 Flash",  0.75,  3.75, 0.10, 1.00),
    # Anthropic: cache read 0.1×, cache write 1.25× (5분 TTL).
    "haiku":       Model("Claude Haiku 4.5",  1.00,  5.00, 0.10, 1.25),
}

DEFAULT = "sonnet"


def get(key: str = DEFAULT) -> Model:
    if key not in MODELS:
        raise SystemExit(
            f"알 수 없는 모델 '{key}'. 사용 가능: {', '.join(MODELS)}"
        )
    return MODELS[key]


def cost(model: Model, inp_tok: int, out_tok: int,
         cached_tok: int = 0, batch: bool = False) -> float:
    """USD 비용. cached_tok 은 inp_tok 중 캐시 읽기로 처리되는 부분."""
    fresh = max(inp_tok - cached_tok, 0)
    usd = (fresh * model.inp
           + cached_tok * model.inp * model.cache_read
           + out_tok * model.out) / 1e6
    return usd * (model.batch if batch else 1.0)


def usd(x: float, digits: int = 4) -> str:
    return f"${x:,.{digits}f}"
