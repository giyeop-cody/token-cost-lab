# 출처 (Sources)

이 저장소와 발표 자료에서 인용한 모든 근거의 원본 제목과 링크입니다.
자체 실측(exp01~exp08)이 아닌 모든 수치는 아래 출처를 병기합니다.

인용 원칙:
- 외부 수치는 **원문 제목 + 저자 + 링크**를 함께 적는다.
- 자체 시뮬레이션과 외부 실측을 **반드시 구분**해서 말한다.
- 가격은 수시로 바뀌므로 **확인 날짜**를 병기한다. (이 문서 기준일: 2026-08)

---

## 1. 학술 문헌

### 1.1 토크나이저와 언어 불평등

**Language Model Tokenizers Introduce Unfairness Between Languages**
Aleksandar Petrov, Emanuele La Malfa, Philip H.S. Torr, Adel Bibi (University of Oxford) · NeurIPS 2023
https://arxiv.org/abs/2305.15425

- 동일한 내용의 텍스트가 언어에 따라 토큰 길이 **최대 15배** 차이.
- 일부 언어 사용자는 영어 대비 **최소 2.5배** 비용을 지불.
- 다국어 지원을 표방한 토크나이저에서도 최대 13배 편차가 남음.
- 포르투갈어처럼 영어와 가까운 언어조차 토큰 수 +50%.

> 관련 실험: `exp01_tokenizer_ko_en.py`

---

### 1.2 추론 언어와 정확도

**When Models Reason in Your Language: Controlling Thinking Language Comes at the Cost of Accuracy**
XReasoning 벤치마크 · 2025
https://arxiv.org/abs/2505.22888
코드: https://github.com/Betswish/mCoT-XReasoning

- 프롬프트로 사용자 언어 사고를 강제하면 언어 일치율 **46% → 98%**로 상승.
- 그러나 정확도는 **26% → 17%**로 하락.
- 비영어 질의라도 **영어로 추론할 때 정확도가 일관되게 높음**.
- 100개 사례 post-training으로 완화해도 정확도 손실이 남음.
- 평가 대상: Distilled-R1 / Skywork-OR1 계열 6개 모델.

**Language Matters: How Do Multilingual Input and Reasoning Paths Affect Large Reasoning Models?**
2025
https://arxiv.org/abs/2505.17407

- 영어·중국어가 LRM의 **"reasoning hub"** 언어로 작동.
- 수학·지식 과제에서 hub 언어 추론이 정확도를 **최대 +26.8%** 개선
  (DeepSeek-R1-Distill-Llama-8B 기준 평균 개선폭).
- 반대로 비hub 언어 추론은 독성 탐지·문화 이해 과제에서 유리 —
  **성능/안전성 트레이드오프** 존재.
- 사고 언어 제어 방법으로 prefilling 기법 제안.

> 위 두 편은 서로 반대 방향에서 같은 결론에 도달합니다.
> 관련 슬라이드: 원칙 ① / 트레이드오프

---

### 1.3 컨텍스트 배치

**Lost in the Middle: How Language Models Use Long Contexts**
Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, Percy Liang (Stanford) · TACL vol.12 (2024), NAACL 2024
https://arxiv.org/abs/2307.03172

- 관련 정보가 컨텍스트 **중간**에 위치하면 성능이 급락 (U자 곡선).
- 컨텍스트가 길수록 추가 성능 저하.
- 실무 함의: 핵심 지시는 **맨 앞 또는 맨 뒤**에 배치.

> 관련 실험: `exp03_prompt_caching.py`, `exp07_analyze_my_prompt.py`

---

### 1.4 모델 라우팅

**RouteLLM: Learning to Route LLMs with Preference Data**
Isaac Ong, Amjad Almahairi, Vincent Wu, Wei-Lin Chiang, Tianhao Wu, Joseph E. Gonzalez, M. Waleed Kadous, Ion Stoica (UC Berkeley · Anyscale · Canva) · ICLR 2025
https://arxiv.org/abs/2406.18665

- Chatbot Arena 인간 선호 데이터로 강/약 모델 이진 라우터 학습.
- **비용 2배 이상 절감, 응답 품질 유지**.
- 평가 지표: CPT(Call-Performance Threshold), APGR.
- 실험 구성: 강 = gpt-4-1106-preview, 약 = Mixtral-8x7B.

> 관련 실험: `exp06_other_levers.py`

---

### 1.5 프롬프트 압축

**LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models**
Huiqiang Jiang, Qianhui Wu, Chin-Yew Lin, Yuqing Yang, Lili Qiu (Microsoft Research) · EMNLP 2023
https://arxiv.org/abs/2310.05736

- **최대 20× 압축에 성능 손실 1.5포인트**.
- coarse-to-fine 방식, budget controller + 반복적 토큰 단위 압축.

**LongLLMLingua: Accelerating and Enhancing LLMs in Long Context Scenarios via Prompt Compression**
Huiqiang Jiang 외 (Microsoft Research)
https://arxiv.org/abs/2310.06839

- 질문 인지형(query-aware) 압축으로 롱컨텍스트 시나리오 대응.

**LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression**
Zhuoshi Pan, Qianhui Wu, Huiqiang Jiang 외 (Microsoft Research) · ACL 2024 Findings
https://arxiv.org/abs/2403.12968
코드: https://aka.ms/LLMLingua-2

- 압축을 **토큰 분류 문제**로 정식화. XLM-RoBERTa-large / mBERT 기반.
- **압축률 2~5×**, 기존 압축법 대비 **3~6배 빠름**, end-to-end 지연 1.6~2.9× 개선.

> ⚠️ **자주 발생하는 인용 오류**: "20× 압축"은 원본 LLMLingua(2310.05736)의 결과입니다.
> LLMLingua-2(2403.12968)는 2~5× 압축이며 속도에 초점을 둔 후속작입니다. 둘을 구분해서 인용하세요.

---

### 1.6 시맨틱 캐싱

**GPT Semantic Cache: Reducing LLM Costs and Latency via Semantic Embedding Caching**
Sajal Regmi, Chetan Phakami Pun · 2024
https://arxiv.org/abs/2411.05276

- 쿼리 임베딩을 Redis 인메모리에 저장해 의미가 유사한 질의를 매칭.
- **API 호출 최대 68.8% 감소**, 캐시 히트율 61.6~68.8%.
- positive hit rate **97% 이상** (캐시된 응답의 신뢰성).

> 관련 실험: `exp06_other_levers.py`

---

## 2. 벤더 공식 문서

> 아래 수치는 모두 2026-08 기준입니다. **인용 전 반드시 재확인하세요.**

### 2.1 프롬프트 캐싱

| 제공사 | 캐시 읽기 | 캐시 쓰기 | 최소 토큰 | 방식 |
|---|---|---|---|---|
| Anthropic | 0.1× (90% 할인) | 1.25× (5분) / 2× (1시간) | 1,024 | 명시적 `cache_control` |
| OpenAI | 0.5× (50%) ~ 0.1× (신형) | 없음 | 1,024 | 자동 프리픽스 감지 |
| Google | 약 0.25× (75% 할인) | 별도 | 모델별 상이 | implicit / explicit |
| DeepSeek | 0.1× (90% 할인) | 없음 | — | 자동 |

- **Anthropic — Prompt caching**
  https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
- **OpenAI — Prompt caching**
  https://platform.openai.com/docs/guides/prompt-caching
- **Google — Gemini context caching**
  https://ai.google.dev/gemini-api/docs/caching

> 관련 실험: `exp03_prompt_caching.py`

---

### 2.2 배치 API

- **Anthropic — Message Batches API**
  https://docs.anthropic.com/en/docs/build-with-claude/batch-processing
  50% 할인 · 최대 24시간 · 배치당 10만 요청 · 결과 29일 보관 · 캐싱과 중첩 적용 가능.
- **OpenAI — Batch API**
  https://platform.openai.com/docs/guides/batch
  50% 할인 · 24시간 SLA · 배치당 5만 요청 · JSONL 업로드 방식.

> 관련 실험: `exp06_other_levers.py`

---

### 2.3 토큰 사용량 계측 (Gemini)

- **Gemini API — Understanding and counting tokens**
  https://ai.google.dev/gemini-api/docs/tokens
- **GenerateContentResponse.UsageMetadata 필드 레퍼런스**
  https://ai.google.dev/api/generate-content#UsageMetadata

`usageMetadata` 주요 필드:

| 필드 | 의미 |
|---|---|
| `promptTokenCount` | 입력 토큰 (시스템 지시·히스토리 포함, **캐시 토큰도 포함**) |
| `candidatesTokenCount` | 생성된 응답 토큰 |
| `thoughtsTokenCount` | **사고(thinking) 토큰 — 출력 단가로 과금** |
| `cachedContentTokenCount` | 캐시에서 읽은 토큰 |
| `toolUsePromptTokenCount` | 함수 호출·코드 실행이 내부적으로 소비한 입력 토큰 |
| `totalTokenCount` | 위 항목의 합 |

> ⚠️ `promptTokenCount`는 캐시 토큰을 **이미 포함**합니다.
> 실제 과금 입력 = `promptTokenCount − cachedContentTokenCount`.
> 이 차감을 빠뜨리면 캐싱 절감 효과가 보이지 않습니다.

> 관련 실험: `exp08_gemini_live.py` (실제 API 호출로 위 필드를 직접 관측)

---

### 2.4 가격 페이지

- Anthropic — https://www.anthropic.com/pricing
- OpenAI — https://openai.com/api/pricing
- Google Gemini — https://ai.google.dev/pricing
- DeepSeek — https://api-docs.deepseek.com/quick_start/pricing

> 단가 테이블 위치: `lab/pricing.py` (이 저장소의 유일한 가격 진실 공급원)

---

## 3. 엔지니어링 자료

**Effective context engineering for AI agents** (Anthropic Engineering, 2025-09)
https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

- **context rot**: 컨텍스트 토큰이 늘수록 정보 회수 정확도가 떨어짐 (모든 모델에서 관측).
- **attention budget**: 트랜스포머의 n² 관계로 인해 컨텍스트는 유한 자원.
- 롱호라이즌 전략 3종: **컴팩션 / 구조적 노트 작성 / 서브에이전트**.
- 서브에이전트는 수만 토큰을 탐색해도 **1,000~2,000 토큰의 요약만 반환**.

**How we built our multi-agent research system** (Anthropic Engineering, 2025)
https://www.anthropic.com/engineering/multi-agent-research-system

- 에이전트는 일반 챗 대비 약 **4배**, 멀티에이전트는 약 **15배** 토큰 소모.

> 관련 실험: `exp04_agent_loop_sdd.py`

---

## 4. 반증 · 한계 자료

> 유리한 근거만 모으면 검증이 아니라 영업입니다. 반대 방향 근거도 함께 싣습니다.

**Spec-Kit vs OpenSpec 토큰 벤치마크** (2026)

- 스펙 주도 개발(SDD) 도구 간 토큰 소비 비교에서 Spec-Kit이 OpenSpec 대비 **토큰 +97~109%**.
- 시사점: SDD가 항상 절감이 아니며, **무거운 프레임워크는 역효과**.

**ETH Zurich — LLM 생성 컨텍스트 파일 연구**

- LLM이 자동 생성한 컨텍스트/규약 파일은 성공률을 소폭 떨어뜨리면서 **비용은 20%+ 증가**.
- 시사점: 컨텍스트 파일은 **사람이 짧게** 쓸 때만 이득.

> 관련 슬라이드: "SDD는 조건부로만 참이다"

---

## 5. 자체 실측

**token-cost-lab** — 이 저장소.

- `exp01`~`exp07`: tiktoken(o200k_base / cl100k_base) 기반 실측 + 단가 시뮬레이션.
- `exp08`: **Gemini API 실제 호출** — 실시간 토큰 사용량 및 비용 관측.
- 한·영 문장쌍 데이터: `data/sentence_pairs.json`.

시뮬레이션 결과는 "가정에 기반한 계산"이고, `exp08`만이 "실제 청구되는 값"입니다.
발표 시 이 둘을 구분해서 말하세요.
