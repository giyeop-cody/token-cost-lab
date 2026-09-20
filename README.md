# token-cost-lab

**LLM 토큰 비용을 줄이는 원칙을, 관측과 가정을 구분해서 재현하는 실험 모음.**

[English](README_EN.md) · [실측·저장 로그](LIVE_RESULTS.md) · [상세 정정 보고서](docs/CORRECTIONS.md) · [격리 주장 재확인](docs/REASSERTED.md) · [발표 자료](presentation/README.md) · [출처](SOURCES.md)

## 주장은 유지합니다

1. **영어 활용:** 대응 내용의 토큰 비용이나 추론 정확도에 유리한 경우가 있습니다. 모델·과제별로 확인하세요.
2. **KISS/DRY/YAGNI:** 불필요한 코드, 전체 재출력, 반복 재작업을 줄이세요.
3. **설명·사고 예산 조절:** 필요한 출력만 받고 정확도 게이트를 함께 두세요.
4. **스펙 선주입:** 짧고 결정적인 요구사항을 먼저 정하세요. 작성 비용과 실제 재작업 감소를 함께 측정하세요.
5. **캐싱·컨텍스트 관리·라우팅:** 조건에 맞을 때 적용하고 전체 비용·품질로 검증하세요.

‘한국어가 항상 비싸다’, ‘사고 토큰이 길면 더 깊게 생각한다’, ‘모든 정책이 품질을 유지하며 같은 비율로 절감된다’는 보장은 아닙니다.


초기 패키지·브라우저·tiktoken 인코딩 파일 설치에는 네트워크가 필요할 수 있지만 LLM API 과금은 없습니다.

## 2026-09-20 정정의 핵심

| 근거 종류 | 확인된 내용 | 범위 |
|---|---|---|
| **새 로컬 실측** | FLORES-200 대응 번역문 1,012쌍: KO/EN **1.4723배**(`o200k_base`), **2.3669배**(`cl100k_base`) | 토크나이저 인코딩. Gemini·Claude 생성 비용 실측 아님 |
| **기존 API 로그 재계산** | 간단한 계산 1문제, 자동/미지정: 공식 Standard **199.47배**, 기존 발표 환산 **240.02배** | 허용오차 통과 각각 6/6. 명시적 0은 5/6, 정확도 동등성 증명 아님 |
| **통계 교정** | reason 문자당 비용 p: **6.08e-10 → 4.02e-7** | 기존 단가 고정, 정규근사 → Welch t분포. 네 비교의 유의성 유지 |
| **외부 정확도 연구** | 한국어 MATH-500의 영어/한국어 사고 유도 평균 **83.7% / 75.4%** | *Language Matters* 표 1, 네 모델. 이번 저장소에서 모델 재실행한 결과 아님 |
| **시나리오** | 페르소나 **20.8배**·SDD **약 71%**는 과거 가정으로 보존 | 수정 기본은 19.0배·68.7%. 실제 품질 동등 정책 A/B가 아님 |

**이번 정정의 새 유료 API 호출은 0회입니다.** 저장된 API 원자료 110행은 그대로 보존합니다.
문자당 비용은 의미량 정규화가 아니며, 호출당 비용이 낮다는 관측을 ‘착시’로 지우지 않습니다.

## 빠른 시작 — 무과금

Python **3.10+**.

```bash
git clone https://github.com/giyeop-cody/token-cost-lab.git
cd token-cost-lab
pip install -r requirements.txt
python run_all.py                      # 기본값은 API 호출 없음
python tools/parallel_tokenizer_bench.py
python tools/stats_test.py results/live_lang_thinking.jsonl
python tools/thinking_sweep.py --summarize results/thinking_sweep.jsonl
python demo/compare_personas.py
python demo/compare_personas.py --scenario legacy  # 20.8배: 과거 가정 재현
```

`run_all.py --live`나 개별 live 명령은 유료 호출을 할 수 있습니다. 저장 로그 재계산과 새 요청을 구분하세요.

## 실험과 증거 등급

| 파일 | 내용 | 증거 |
|---|---|---|
| `exp01_tokenizer_ko_en.py` | 저장소 예문 6쌍의 인코딩 | 로컬 토크나이저 실측; 전체 언어 일반화 금지 |
| `tools/parallel_tokenizer_bench.py` | FLORES-200 1,012쌍 | 새 로컬 실측, 원문·해시·문장별 토큰·라이선스 포함 |
| `exp02_output_to_input.py` | 입력으로 결정 전달, 출력 절감 | 토큰 가정의 비용 계산 |
| `exp03_prompt_caching.py` | 캐시 최소 길이·히트율·첫 쓰기 | 비용 시나리오; 저장료·품질 별도 |
| `exp04_agent_loop_sdd.py` | 턴 누적·스펙 작성·컴팩션 | 40→12턴 등은 가정. `--warm-cache`는 과거 예열 가정 |
| `exp05_verbosity_effort.py` | 출력 길이·effort·툴 스키마 | 일부 인코딩 + 가정 기반 비용 |
| `exp06_other_levers.py` | Batch·압축·캐싱·라우팅 적층 | 비용 시나리오. 상호작용·품질 미측정 |
| `exp07_analyze_my_prompt.py` | 내 프롬프트 진단 | 인코딩 + 휴리스틱; 실제 캐시 적중 보장 아님 |
| `exp08_gemini_live.py` | Gemini count/generate usage | 키가 있을 때 실제 요청; 기본 모델 ID와 가격 연결 |
| `exp09_dry.py` | diff·리워크·압축+캐시 | 비용 시나리오 |
| `exp10_thinking_cross_vendor.py` | 3벤더 usage 비교 | live 실행 시 기록. dry-run/mock을 live 측정으로 부르지 않음 |
| `exp11_tool_output_bloat.py` | 툴 본문 누적·전체 시스템 비용 | A는 시나리오, `--live`는 3요청 관측 |

파일은 `experiments/`에 있습니다. 예:

```bash
python experiments/exp03_prompt_caching.py --model haiku --static 3000
python experiments/exp07_analyze_my_prompt.py --demo
python experiments/exp10_thinking_cross_vendor.py --dry-run
python experiments/exp11_tool_output_bloat.py --turns 40 --tool-tokens 20000
```

## 검증 — 실패를 성공으로 표시하지 않기

```bash
pip install -r requirements-dev.txt
python -m playwright install --with-deps chromium
python tools/reproduce_audit.py         # 로그 재계산·보고서·PPTX/대본 재생성, 무과금
python -m pytest -q
python demo/vibe_vs_spec/verify_ac.py    # 문자열 검사 + 실제 브라우저 AC
python tools/verify_deck.py              # 실제 PPTX 모든 텍스트와 근거 대조
```

PDF 재생성: LibreOffice와 Nanum 폰트를 설치한 뒤
`python presentation/deckgen/make_pdf.py --check`.
기존 PDF까지 검증하려면 `python tools/verify_deck.py --with-pdf`.

- 실제 PPTX의 `240→999` 변조, 모바일 `1열→2열` 변조, 무동작 메모를 거부하는 회귀 테스트가 있습니다.
- 실패 assertion은 nonzero 종료입니다. 의존성 부족·실행 생략은 PASS가 아닙니다.
- 검증 범위와 실행 결과는 `results/verification.json`에 기록합니다. 테스트 개수를 영구 보증처럼 고정하지 않습니다.
- 전체 로컬 게이트와 실행 기록: `python tools/check_audit.py` → `results/verification.json`.
- CI: `.github/workflows/ci.yml` — 같은 검사를 유료 API 호출 없이 수행하도록 추가했습니다. 원격 CI 실행 상태와 로컬 성공은 구분합니다.

## 요금 계산 원칙

`lab/pricing.py`에 공식 가격 스냅샷과 **별도로 명명한 과거 환산/티어 시나리오**가 있습니다.
[기준일·범위](docs/PRICING.md)를 함께 보세요. 최신 flagship 별칭과 개별 모델 ID를 혼용하지 않습니다.

Gemini의 `promptTokenCount`는 캐시 입력을 포함합니다.

```text
비캐시 입력 = prompt - cached
비용 = 비캐시 입력 × 입력 단가 + cached × 캐시 단가
       + (candidates + thoughts) × 출력 단가
```

캐시를 입력에서 두 번 빼지 않습니다. `toolUsePromptTokenCount`를 로컬 함수 응답 크기나
추가 청구액으로 자동 간주하지 않습니다. 전체 캐시 적격성은 모델별로 다릅니다(예: Haiku 4.5는 4,096).

## 하지 않은 검증

새 상용 모델의 한/영 정확도 재현, 실제 정책 A/B, 실제 청구서 대조, 다양한 과제의 품질 동등성 검정은
이번 정정에서 하지 않았습니다. 기존 N=5·N=100 예비 기록의 누락 원자료도 새로 만들어 채우지 않았습니다.
단가 환산은 무료 티어·계약·세금·구독료·장문 할증·도구 사용료를 모두 포함한 실제 청구액과 다를 수 있습니다.

가격이나 과제가 바뀌면 배수도 바뀝니다. **주장을 유지하는 가장 좋은 방법은, 근거가 실제로 말하는 범위를 정확히 지키는 것입니다.**
