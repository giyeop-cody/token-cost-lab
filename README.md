# token-cost-lab

**LLM 토큰 비용 절감 기법을, 남의 블로그 숫자 대신 내 손으로 재보는 실험 모음.**

발표 자료 *"확실하게 토큰 사용량을 줄이는 방법"* 의 부속 저장소입니다.
발표에 나온 모든 수치는 이 저장소의 스크립트로 재현할 수 있습니다.

```bash
git clone <this-repo> && cd token-cost-lab
pip install -r requirements.txt
python run_all.py
```

API 키가 필요 없습니다. 토크나이저 실측 + 공개 단가 기반 시뮬레이션으로 동작합니다.

---

## 왜 이걸 만들었나

토큰 절감 글은 많은데, 대부분 이렇게 끝납니다. *"프롬프트 캐싱을 쓰면 90% 절감됩니다."*

문제는 그 90%가 **어떤 프리픽스 길이에서, 몇 번의 호출에서, 어떤 히트율일 때** 나온 숫자인지
아무도 말해주지 않는다는 점입니다. 파라미터가 바뀌면 90%는 18% 손해로도 뒤집힙니다
(실험 03의 E절이 그 경우입니다).

이 저장소는 **모든 가정을 명령줄 인자로 노출**합니다. 자기 팀의 실제 숫자를 넣고 다시 돌리세요.

---

## 실험 목록

| # | 파일 | 무엇을 재는가 | 근거 문헌 |
|---|---|---|---|
| 01 | `exp01_tokenizer_ko_en.py` | 한국어/영어 토큰 배수 (tiktoken 실측) | [Petrov+ NeurIPS'23](https://arxiv.org/abs/2305.15425) |
| 02 | `exp02_output_to_input.py` | 출력→입력 환전, 손익분기 | 벤더 [가격표](#4-가격-페이지) |
| 03 | `exp03_prompt_caching.py` | 캐싱 절감 곡선, 캐시 파괴 대가 | [Anthropic](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) · [OpenAI](https://platform.openai.com/docs/guides/prompt-caching) · [Lost in the Middle](https://arxiv.org/abs/2307.03172) |
| 04 | `exp04_agent_loop_sdd.py` | 루프의 2차 함수 비용, SDD, YAGNI | [Anthropic 컨텍스트 엔지니어링](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| 05 | `exp05_verbosity_effort.py` | 설명 길이, reasoning effort, 툴 스키마 | [XReasoning](https://arxiv.org/abs/2505.22888) · 벤더 문서 |
| 06 | `exp06_other_levers.py` | Batch·압축·시맨틱캐싱·라우팅·적층 | [RouteLLM](https://arxiv.org/abs/2406.18665) · [LLMLingua](https://arxiv.org/abs/2310.05736) · [GPT Semantic Cache](https://arxiv.org/abs/2411.05276) |
| 07 | `exp07_analyze_my_prompt.py` | **내 프롬프트 파일을 직접 진단** | [Lost in the Middle](https://arxiv.org/abs/2307.03172) |
| 08 | `exp08_gemini_live.py` | **실제 Gemini API 호출 → 진짜 청구 토큰** | [Gemini 토큰 문서](https://ai.google.dev/gemini-api/docs/tokens) |

각 항목의 정확한 인용 정보는 **[SOURCES.md](SOURCES.md)** 에 정리되어 있습니다.

실전 케이스 스터디: **[demo/vibe_vs_spec/](demo/vibe_vs_spec/)** — 같은 페이지를 자유 지시(Vibe)와
결정적 스펙(Spec)으로 각각 생성해 토큰·비용을 비교. 짧은 4필드 스펙은 토큰 +1.8%에
비용 −8.3%로, exp04(SDD)와 반증 절의 결론("짧고 결정만 담은 스펙을 써라")을 지지한다.

### 개별 실행

```bash
python experiments/exp01_tokenizer_ko_en.py
python experiments/exp02_output_to_input.py --model opus --devs 25
python experiments/exp03_prompt_caching.py --static 40000 --calls 500
python experiments/exp04_agent_loop_sdd.py --turns 40
python experiments/exp05_verbosity_effort.py --calls 5000
python experiments/exp06_other_levers.py --calls 100000
python experiments/exp08_gemini_live.py --dry-run       # 구조만 (키 불필요)
python experiments/exp08_gemini_live.py --list-models    # 가용 모델 확인 (무과금)
```

### 07번은 특히 실용적입니다

자기 시스템 프롬프트를 넣으면 캐시를 깨뜨리는 부분을 짚어줍니다.

```bash
python experiments/exp07_analyze_my_prompt.py my_system_prompt.md
python experiments/exp07_analyze_my_prompt.py --demo     # 예제로 먼저 보기
cat CLAUDE.md | python experiments/exp07_analyze_my_prompt.py -
```

출력 예:

```
── 3. 캐시 파괴 요소 — 앞쪽의 동적 값
  위치       문서상 위치  종류            값
  🔴 앞부분           7%  타임스탬프      2026-08-14 09:31
  🔴 앞부분          12%  요청/세션 ID    req_8f3a21c9
  🔴 앞 1/3 구간에 동적 값 5건. 캐시 히트율이 0에 가까워진다.
```

### 08번은 유일하게 "진짜 청구서"를 봅니다

> **실측 완료(2026-08-15)**: 실제 호출 결과는 **[LIVE_RESULTS.md](LIVE_RESULTS.md)** 에 있습니다.
> 하이라이트 — 같은 질문에 사고 예산만 바꿨더니 응답은 4~5토큰으로 동일한데
> **비용이 37배** 차이났습니다. 전액이 화면에 안 보이는 `thoughtsTokenCount` 입니다.
>
> ⚠️ `gemini-2.5-*` 는 신규 키에서 404 입니다. `--list-models` 로 가용 모델을 먼저 확인하세요.

01~07번은 전부 시뮬레이션입니다. **08번만 실제 Gemini API를 호출**해서
`usageMetadata` 에 찍힌 진짜 토큰 수를 읽습니다.

```bash
export GEMINI_API_KEY="..."        # https://aistudio.google.com/apikey (무료 등급 있음)

python experiments/exp08_gemini_live.py --dry-run     # 구조만, 키·과금 불필요
python experiments/exp08_gemini_live.py --count-only  # 입력 토큰만, 과금 없음
python experiments/exp08_gemini_live.py               # 한/영 실호출 비교
python experiments/exp08_gemini_live.py --thinking    # 사고 예산별 토큰
python experiments/exp08_gemini_live.py --prompt "$(cat my_prompt.md)"
```

발표 중 라이브 시연에는 `--thinking` 이 가장 잘 먹힙니다.
사고 예산만 바꿔 같은 질문을 세 번 던지면, **응답에는 보이지 않는 사고 토큰이
출력 요금에 그대로 더해지는 것**이 표로 나옵니다.

```
  사고 예산    사고 tok  응답 tok  출력계  비용
  -----------  --------  --------  ------  ---------
  사고 끔 (0)         0        30      30  $0.000355
  제한 512          480        30     510  $0.005155
  자동 (-1)         640        30     670  $0.006755
```

**계측할 때 틀리기 쉬운 두 가지:**

1. `promptTokenCount` 는 캐시 토큰을 **이미 포함**합니다.
   실제 과금 입력 = `promptTokenCount − cachedContentTokenCount`.
   이걸 빼지 않으면 캐싱을 켜도 절감이 장부에 안 보입니다.
2. 스트리밍에서 `usageMetadata` 는 **청크마다 누적값**으로 옵니다.
   합산하지 말고 **마지막 청크 값만** 쓰세요. (일부 SDK는 `cachedContentTokenCount` 가
   0이 아니라 `undefined` 로 옵니다.)

---

## 발표의 핵심 주장과 검증 결과

| # | 주장 | 판정 | 근거 |
|---|---|---|---|
| ① | 추론은 영어로 시켜라 | **참**, 단 배수는 모델마다 다름 | o200k에서 한국어 1.44배, cl100k 2.22배 (exp01) · [Petrov+ 2023](https://arxiv.org/abs/2305.15425) |
| ② | KISS/DRY/YAGNI를 지켜라 | **참**, 단 근거는 단가가 아닌 턴 수 | 안 쓰는 코드는 매 턴 재전송된다 (exp04-D) |
| ③ | 장황한 설명을 금지하라 | **참** | 설명만 줄여 출력 40~60% 감소 (exp05-A) |
| ④ | 웹에서 추론시키고 결과를 주입하라 | **참** (= SDD) | 턴 수 감소로 기능당 71% 절감 (exp04-B) · [Anthropic 2025](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| ⑤ | 출력을 입력으로 환전하는 게 핵심 | **참** | 입력 3배 늘리고 총비용 66% 절감 (exp02-B) |

### 반증도 같이 싣습니다

이 저장소는 주장을 보강하는 근거만 모으지 않습니다. 반대 증거는 실험 스크립트 안에
`⚠️` 로 함께 출력됩니다.

- **영어 추론이 항상 싸지는 않다** — Qwen3는 중국어 CoT가 영어보다 토큰 40% 적다는 보고가 있습니다.
- **사용자 언어로 사고를 강제하면 정확도가 떨어진다** — XReasoning(arXiv:2505.22888)에서
  언어 매칭률은 46%→98%로 올랐지만 정확도는 26%→17%로 하락했습니다.
- **스펙이 항상 이득은 아니다** — ETH Zurich 연구([SOURCES.md §4](SOURCES.md#4-반증--한계-자료))에서 LLM 생성 컨텍스트 파일은
  성공률을 약간 낮추면서 추론 비용을 20% 이상 올렸습니다. 한 벤치마크에서는
  Spec-Kit이 OpenSpec 대비 토큰을 최대 2배 썼습니다.
  → 결론은 "스펙을 써라"가 아니라 **"짧고, 설명이 아닌 결정만 담은 스펙을 써라"** 입니다.
- **캐싱은 잘못 쓰면 손해다** — 동적 값이 프리픽스 앞에 있으면 쓰기 프리미엄만 매번 물어
  캐시를 안 쓴 것보다 18% 비싸집니다 (exp03-E).

---

## 오늘 바로 할 수 있는 것 (우선순위)

| 순위 | 레버 | 난이도 | 리스크 | 적용 조건 |
|---|---|---|---|---|
| 1 | 프롬프트 캐싱 | 낮음 | 없음 | 고정 프리픽스 1K tok 이상 |
| 2 | verbosity / reasoning effort | 낮음 | 낮음 | 설정 한 줄인 경우가 많음 |
| 3 | Batch API (50% 할인) | 낮음 | 없음 | 지연에 둔감한 잡이 있는가 |
| 4 | 스펙 먼저 (SDD) | 중간 | 낮음 | 재작업이 3사이클 이상인가 |
| 5 | 컨텍스트 컴팩션 | 중간 | 중간 | 세션이 20턴을 넘는가 |
| 6 | 모델 라우팅 | 높음 | 중간 | 품질 측정 도구가 있는가 |
| 7 | 시맨틱 캐싱 | 높음 | 높음 | 질의 반복률 20% 이상인가 |
| 8 | 프롬프트 압축 | 높음 | 중간 | RAG 컨텍스트가 10K tok 이상인가 |

1~3번은 오후에 켜고 되돌릴 수 있습니다. 6~8번은 품질 측정 체계가 먼저 필요합니다.

---

## 가격 정보 갱신

모든 단가는 **`lab/pricing.py` 한 곳**에만 있습니다. 2026-08 공개 리스트 기준이며,
가격은 자주 바뀌므로 발표나 보고 전에 아래 공식 페이지에서 확인하고 갱신하세요.

- [Anthropic](https://www.anthropic.com/pricing) ·
  [OpenAI](https://openai.com/api/pricing) ·
  [Google Gemini](https://ai.google.dev/pricing) ·
  [DeepSeek](https://api-docs.deepseek.com/quick_start/pricing)

```python
MODELS = {
    "sonnet": Model("Claude Sonnet 4.6", 3.00, 15.00, 0.10, 1.25),
    #                                    입력  출력   캐시읽기 캐시쓰기
}
```

모델을 추가하면 모든 실험에서 `--model <키>` 로 바로 쓸 수 있습니다.

---

## 이 저장소가 하지 않는 것

정직하게 밝힙니다.

- **exp01~07은 실제 API를 호출하지 않습니다.** 토큰 수는 tiktoken 실측이지만, 비용은
  공개 단가 기반 시뮬레이션입니다. 워크플로별 토큰 수(예: "대충 지시하면 출력 12,000 tok")는
  전형적인 값을 가정한 것이지 측정값이 아닙니다.
  실제 청구되는 값을 보려면 **exp08**(Gemini API 실호출)을 쓰세요. 단, exp08의
  단발 호출은 표본 1개이므로 여러 번 돌려 평균으로 말해야 합니다.
- **품질을 측정하지 않습니다.** 비용만 봅니다. effort를 낮추거나 압축을 세게 걸면
  정확도가 떨어질 수 있고, 그 손실은 여기서 잡히지 않습니다.
- **Anthropic 토크나이저를 직접 쓰지 않습니다.** 공개 라이브러리가 없어 tiktoken으로
  근사했습니다. 외부 코퍼스 측정에서 Claude 토크나이저의 한국어 배수는 1.88로,
  o200k보다 나쁩니다. 즉 이 저장소의 한국어 비용 추정은 **보수적인** 쪽입니다.

가장 정확한 방법은 언제나 **자기 계정의 usage 로그**입니다. 이 저장소는
그 로그를 보기 전에 어디를 먼저 볼지 정하는 용도입니다.

---

## 요구 사항

- Python 3.9+
- `tiktoken` (유일한 필수 의존성)

```bash
pip install -r requirements.txt
```

## 구조

```
token-cost-lab/
├── README.md
├── SOURCES.md                   # 인용한 모든 근거의 원본 링크
├── LIVE_RESULTS.md              # 실호출 실측 기록 (2026-08-15)
├── requirements.txt
├── LICENSE                      # MIT
├── run_all.py                   # exp01~09 전체 실행 (무과금)
├── lab/
│   ├── pricing.py               # 단가 테이블 (여기만 고치면 됨)
│   └── report.py                # 콘솔 표 출력 (한글 폭 처리 포함)
├── data/
│   └── sentence_pairs.json      # 한/영 동일 의미 문장 쌍 6개
├── experiments/
│   ├── exp01_tokenizer_ko_en.py   ~ exp07_analyze_my_prompt.py
│   ├── exp08_gemini_live.py       # 실제 API 호출 (키 있을 때만)
│   └── exp09_dry.py               # DRY의 토큰 경제학
├── tools/
│   ├── live_lang_bench.py       # 한·영 × 설명형·추론형 실호출 벤치
│   ├── stats_test.py            # 부트스트랩 CI · Welch · Cliff's δ
│   ├── thinking_sweep.py        # 사고 예산 스윕 (+ Wilson CI · 단가 민감도)
│   └── verify_deck.py           # 슬라이드 수치 회귀 검사
├── results/                     # 실측 원자료 (재실행 없이 검증 가능)
│   ├── live_lang_thinking.jsonl   # 80행
│   ├── thinking_sweep.jsonl       # 30행
│   ├── stats_thinking.txt · sweep_summary.txt
└── demo/                        # 페르소나 A/B 토큰 비교
    ├── compare_personas.py      # 입력·출력·사고·캐싱 4축 실측 비교
    ├── memo.html                # 두 페르소나가 만든 동일 산출물
    ├── 비교.html                 # 결과 시각화
    ├── qr_repo.png
    └── transcripts/             # 대화 전문 (토큰 계측 원본)
```

### 발표 자료는 `presentation` 브랜치에

덱(pptx/pdf) · 발표 대본 · 검증 보고서는 **`presentation` 브랜치**에 있습니다.
`main`은 *"수치를 재현하는 코드"* 만 담아 가볍게 유지합니다.

```bash
git checkout presentation     # 덱 29장 · PDF · 발표 대본 · 빌드 도구
```

그래서 `main`에서 `tools/verify_deck.py` 를 돌리면 덱 관련 검사는 **SKIP**되고
원자료 검증 87개만 수행합니다. 저장소만 clone해도 정상 동작합니다.

```bash
python tools/verify_deck.py     # main: 87개 통과 · presentation: 98개 통과
```

## 기여

자기 팀의 실측치로 `data/sentence_pairs.json` 을 늘리거나,
`lab/pricing.py` 에 모델을 추가하는 PR을 환영합니다.
외부 수치를 인용할 때는 반드시 출처를 함께 적어주세요 — 원문 제목, 저자, 링크를
**[SOURCES.md](SOURCES.md)** 에 추가하고, 해당 실험 스크립트의 docstring 하단
`출처:` 블록에도 링크를 남기면 됩니다.

## 라이선스

MIT
