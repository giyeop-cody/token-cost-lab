# 가격 스냅샷과 비용의 범위

확인일 **2026-09-20**. 코드의 기준 파일은 `lab/pricing.py`다.
현재 페이지를 확인한 날짜와 예전 실험의 측정일(2026-08-15)을 혼용하지 않는다.

## 모델 ID에 연결된 단가

USD / 1M tokens, 텍스트·짧은 컨텍스트 기본 조건. 표에는 캐시 저장료나 별도 도구료가 없다.

| 키 / API ID | 입력 | 출력 (사고 포함) | 캐시 읽기/입력 | 비고 |
|---|---:|---:|---:|---|
| flash-lite / gemini-3.1-flash-lite | 0.25 | 1.50 | 0.10 | Standard text; audio 입력은 별도 |
| gemini-25 / gemini-2.5-pro | 1.25 | 10 | 0.10 | ≤200k 컨텍스트; 권한·가용성 별도 |
| gemini-pro / gemini-3.1-pro-preview | 2 | 12 | 0.10 | ≤200k |
| gemini-35f / gemini-3.5-flash | 1.50 | 9 | 0.10 | Standard |
| gemini-36f/37f/38f | 0.75 | 3.75 | 0.10 | 공개 introductory 조건; 사용 시 공식 적용 기간 재확인 |
| sonnet / claude-sonnet-4-6 | 3 | 15 | 0.10 | 5분 캐시 쓰기 1.25배; 최소 1,024 |
| opus / claude-opus-4-6 | 5 | 25 | 0.10 | 5분 캐시 쓰기 1.25배; 최소 4,096 |
| haiku / claude-haiku-4-5 | 1 | 5 | 0.10 | 5분 캐시 쓰기 1.25배; 최소 4,096 |
| gpt5 / gpt-5 | 1.25 | 10 | 0.10 | GPT-5.x flagship이라는 가상의 공통 가격 아님 |
| deepseek / deepseek-flash | 0.30 | 1.20 | 0.02 | V4.1 Flash peak. off-peak는 0.15/0.60 |

공식 출처:
- https://ai.google.dev/gemini-api/docs/pricing
- https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- https://developers.openai.com/api/docs/pricing.md
- https://api-docs.deepseek.com/quick_start/pricing/

Gemini 3.5–3.8 Flash와 3.1 Pro의 공식 implicit cache 최소값은 4,096,
2.5 Pro는 2,048이었다. Flash-Lite의 최소값은 이때 확인한 캐시 표에 없어서 `None`으로 둔다.
이는 캐싱 불가능이라는 뜻이 아니라, **할인을 보장하는 시나리오 입력을 임의로 정하지 않겠다**는 뜻이다.
실제 usage에 캐시 읽기가 기록되어 있으면 그 관측값을 계산에 사용한다.

## 별도로 보존하는 가정

- `LEGACY_TALK`: $1.25/$10 환산. 실제 Flash-Lite 가격이 아니다. **240.02배**의 재현용이다.
- `TIER_SCENARIOS`: SMALL $0.15/$0.60, MID $1.25/$10, LARGE $5/$30 등 과거 정책 예산 가정.
  특정 현행 모델의 공식 단가가 아니며, EXTERNAL=0은 추가 종량 API 비용만 0으로 두는 가정이다.
  구독료·사람 시간은 제외다.
- `demo/vibe_vs_spec/usage.json`의 가격 필드는 원 사례의 환산 조건이다. 새 요금표로 소급 수정하지 않는다.

**199.47배**는 같은 로그에 실제 모델의 2026-09-20 Standard 단가를 적용한 값이다.
240→199의 차이가 모두 ‘시간에 따른 실제 모델의 요금 인하’ 때문이라고 입증한 것은 아니다.
기존부터 서로 다른 모델의 단가를 환산 기준으로 썼다는 문제를 분리해서 표시한다.

## 계산과 제한

`cost(model, inp_tok, out_tok, cached_tok)`의 `inp_tok`은 캐시를 **포함한 전체 입력**이다.
음수 또는 `cached_tok > inp_tok`는 오류로 거부한다.
Claude의 `input_tokens`는 캐시 read/write를 제외한 필드이므로 합쳐서 전달하고 write premium을 별도 더한다.

`tiktoken` 인코딩 수가 Gemini/Claude의 네이티브 토큰 수와 같다고 가정하지 않는다.
캐시 최소 길이·미스·TTL·배치·장문 구간·지역 할증·별도 도구료·세금·무료 티어·계약은 실행 조건별로 확인해야 한다.
이 저장소의 단순 토큰 산식은 완전한 청구서 엔진이 아니다. 지원 범위를 넘어서는 API 모델 ID는
다른 모델 단가로 조용히 대체하지 않고 오류를 낸다. 명시적 가격 override는 환산임을 기록한다.
