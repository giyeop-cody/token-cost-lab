# Sources — 원문과 인용 범위

확인일 **2026-09-20**. 로컬 재계산은 `results/audit_metrics.json`, 원자료 해시는 `data/evidence_manifest.json`.
문헌 결과, 로컬 계측, API usage 로그, mock/브라우저 테스트, 비용 시나리오는 서로 다른 증거다.

## 1. 언어·추론

### 1.1 토크나이저

Aleksandar Petrov, Emanuele La Malfa, Philip H. S. Torr, Adel Bibi.
**Language Model Tokenizers Introduce Unfairness Between Languages**. NeurIPS 2023.
https://arxiv.org/abs/2305.15425

언어별 토큰화 효율 격차의 문헌 근거. 특정 한국어 배수를 모든 모델에 옮기는 근거는 아니다.

NLLB Team et al. **No Language Left Behind: Scaling Human-Centered Machine Translation** (2022).
FLORES-200: https://github.com/facebookresearch/flores/tree/main/flores200

이번 로컬 측정은 devtest `eng_Latn`/`kor_Hang`의 1,012쌍 전체.
`data/flores200/README.md`에 다운로드 URL, 해시, CC-BY-SA 4.0 라이선스와 저자 표시를 보존했다.
문장별 토큰 합계를 사용한다. 생성 결과나 추론 정확도 측정이 아니다.

### 1.2 정확도와 사고 언어

**Language Matters: How Do Multilingual Input and Reasoning Paths Affect Large Reasoning Models?** (2025),
https://arxiv.org/html/2505.17407v1#S4.T1

표 1의 한국어 MATH-500: 영어/한국어 prefilling의 네 모델 평균 **83.7% / 75.4%**.
모델별 (EN / KO): Llama-8B 69.8/41.6, Qwen-14B 84.4/83.8, QwQ-32B 90.6/88.2,
Qwen3-30B-A3B 89.8/88.0. 평균은 반올림값이다.
이 범위는 조건부 영어 우위를 지지한다. 더 많은 사고 토큰이 더 깊은 추론이라는 증거가 아니며,
모든 상용 모델·안전성·문화 이해 과제의 영어 우위를 뜻하지 않는다.

**When Models Reason in Your Language: Controlling Thinking Language Comes at the Cost of Accuracy** (2025),
https://arxiv.org/abs/2505.22888 · https://github.com/Betswish/mCoT-XReasoning

사고 언어 제어의 정확도 트레이드오프를 다룬 외부 연구. 저장소에서 이 모델들을 새로 재실행하지 않았다.

## 2. 비용·캐시·API 공식 문서

| 항목 | 원문 | 이 저장소에서 사용하는 범위 |
|---|---|---|
| Gemini 가격 | https://ai.google.dev/gemini-api/docs/pricing | Flash-Lite 3.1 Standard text 입력 $0.25/M, 사고 포함 출력 $1.50/M, 캐시 읽기 $0.025/M |
| Claude 가격·캐시 | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | 모델별 최소 길이, 5분 캐시 쓰기와 읽기. Haiku 4.5 최소 4,096 |
| OpenAI 가격 | https://developers.openai.com/api/docs/pricing.md | 정확한 `gpt-5` 행 $1.25/$0.125/$10; ‘GPT-5.x 최신 flagship’와 혼용하지 않음 |
| DeepSeek 가격 | https://api-docs.deepseek.com/quick_start/pricing/ | V4.1 Flash peak/off-peak 구분. 현재 alias와 가격 연결 |
| Gemini 캐시 | https://ai.google.dev/gemini-api/docs/generate-content/caching | 모델별 implicit 최소 길이, explicit 저장료 별도 |
| Gemini usage | https://ai.google.dev/api/generate-content#UsageMetadata | prompt는 cache 포함. thoughts와 candidates를 구분 |
| Gemini 함수 호출 | https://ai.google.dev/gemini-api/docs/generate-content/function-calling | Content의 role+parts, 모델 Content/signature/id 보존 |
| Gemini 사고 | https://ai.google.dev/gemini-api/docs/generate-content/thinking | 모델에 따라 thinkingBudget/thinkingLevel 지원이 다름 |
| Claude 사고 | https://platform.claude.com/docs/en/build-with-claude/extended-thinking | output_tokens에 사고 포함. output_tokens_details.thinking_tokens가 있으면 관측, 없으면 분리 미확인 |
| OpenAI 추론 | https://developers.openai.com/api/docs/guides/reasoning | reasoning_tokens는 출력 과금 토큰의 부분집합 |
| Batch | https://platform.claude.com/docs/en/build-with-claude/batch-processing | 지원 모델·서비스의 할인·지연 조건; 모든 가격표에 공통 보장하지 않음 |

`lab/pricing.py`와 [PRICING.md](docs/PRICING.md)에 스냅샷 범위를 적었다.
저장 usage × 단가는 실제 청구서 확인이 아니다. 캐시 생성/저장·도구·지역·장문·세금·계약조건은 별도다.
`totalTokenCount`는 캐시와 prompt를 중복 합산하는 산식으로 정의하지 않는다.

## 3. 컨텍스트·최적화 문헌

- Nelson F. Liu et al. **Lost in the Middle: How Language Models Use Long Contexts**, TACL 2024.
  https://arxiv.org/abs/2307.03172 — 관련 정보의 위치와 장문 활용. 모든 상황의 비용 법칙은 아님.
- Isaac Ong et al. **RouteLLM: Learning to Route LLMs with Preference Data**, ICLR 2025.
  https://arxiv.org/abs/2406.18665 — 학습된 라우팅의 조건부 비용/성능 결과.
  저장소의 규칙 라우터에 같은 절감률을 자동 적용하지 않음.
- Huiqiang Jiang et al. **LLMLingua**, EMNLP 2023.
  https://arxiv.org/abs/2310.05736 — 프롬프트 압축. 후속 LLMLingua-2의 결과와 혼용 금지.
- **LongLLMLingua**, https://arxiv.org/abs/2310.06839;
  Zhuoshi Pan et al. **LLMLingua-2**, ACL Findings 2024, https://arxiv.org/abs/2403.12968.
- Sajal Regmi, Chetan Phakami Pun. **GPT Semantic Cache** (2024), https://arxiv.org/abs/2411.05276.
  의미 유사도 캐시의 외부 실험. 우리 워크로드의 hit rate는 따로 측정해야 함.
- Anthropic. **Effective context engineering for AI agents** (2025),
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents.
- Anthropic. **How we built our multi-agent research system** (2025),
  https://www.anthropic.com/engineering/multi-agent-research-system.
  서브에이전트·요약은 메인 컨텍스트만이 아니라 자식 호출과 요약 비용까지 함께 봐야 함.

## 4. 반례와 비교 대상

### 4.1 Spec-Kit 대 OpenSpec

**Is Your “Safe” Choice Burning Your Budget?** (2026-03-18), 외부 블로그의 두 사례.
보고된 총토큰은 57,740 대 120,947 및 91,729 대 181,040으로,
Spec-Kit의 증가가 각각 약 109%, 97%다. 둘 다 SDD 접근이며 **SDD 대 무스펙 비교가 아니다**.
다수 과제의 무작위 시험이나 본 저장소의 재현 실측으로 소개하지 않는다.
[1](https://medium.com/it-chronicles/is-your-safe-choice-burning-your-budget-1cfddf8782e4)

### 4.2 저장소 컨텍스트 파일 연구

Thibaud Gloaguen, Niels Mündler, Mark Müller, Veselin Raychev, Martin Vechev.
**Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?** (2026).

v1 §4.2/Table 2는 LLM 생성 컨텍스트 파일 조건의 평균 비용 증가를 SWE-bench Lite에서 20%,
AGENTbench에서 23%로 보고한다. 사람 작성 파일도 비용이 증가할 수 있다.
따라서 ‘사람이 짧게 쓰면 항상 이득’이나 ‘모든 SDD는 손해’로 일반화하지 않는다.
[4](https://arxiv.org/html/2602.11988v1)

## 5. 로컬 증거와 미실행 영역

- `results/live_lang_thinking.jsonl`, `results/thinking_sweep.jsonl`: 원래 보존된 API usage 투영 로그. 새 호출 아님.
- `results/flores_tokenizers.jsonl`: 새 로컬 인코딩 계측, 모델 API 과금 없음.
- `demo/results*.json`, `analysis/`: 가정 기반 비용 시나리오 / 고정 발화 재생.
- `demo/vibe_vs_spec/usage.json`: 세션 토큰 추정치. API 공급자의 raw billing usage 아님.
- `tests/`, `results/browser_*.json`: 소프트웨어 계약·동작 테스트. 모델 품질 실측 아님.
- 과거 N=5/N=100과 37.5배 예비 기록은 원자료 미포함으로 재검증 보류.

이 구분을 유지하는 것이 핵심 주장과 실측의 일관성을 지키는 방법이다.
