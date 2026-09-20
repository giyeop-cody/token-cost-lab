#!/usr/bin/env python3
"""Canonical Korean evidence reports; numbers are interpolated from primary data."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab.evidence import build


def live_report(e):
    sw = e["thinking_sweep"]
    r = sw["ratios"]
    text = f'''# API 저장 로그 재계산 + 새 로컬 토크나이저 실측

**재계산일 2026-09-20 · 새 유료 API 호출 0회.** 기존 API 기록의 측정일은 2026-08-15다.
원본 `results/live_lang_thinking.jsonl` 80행과 `results/thinking_sweep.jsonl` 30행은 수정하지 않았다.
이들은 저장된 usage 필드 투영값이며 실제 청구서 원본은 아니다.

## 핵심 주장 — 유지하되 증거 범위를 명시

- 대응 번역문에서는 한국어가 더 많은 토큰을 쓰는 경향이 확인된다. 영어 활용의 비용 이점은 유지한다.
- 영어 사고 유도가 추론 정확도에 유리한 외부 연구도 있다. 다만 사고 토큰 수는 추론 깊이의 측정값이 아니다.
- 단순한 문제에서 불필요한 사고는 큰 비용 차이를 만들 수 있다. ‘240배’는 기존 발표 환산 단가라는 조건으로 유지한다.
- 글자 수, 호출당 비용, 의미량, 정확도는 서로 다른 지표다. 하나로 다른 것을 대신하지 않는다.

## 1. 같은 30행, 두 가지 단가

실제 호출 모델: `gemini-3.1-flash-lite`. Standard 텍스트 단가(2026-09-20 확인)는
입력 **$0.25/M**, 사고 포함 출력 **$1.50/M**이다.
[공식 가격표](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.1-flash-lite).

기존 **$1.25/$10**은 발표의 환산 가정으로 보존한다. 이것을 Flash-Lite의 당시 공식 가격이었다고
재해석하지 않는다. 모델/단가 혼용 정정이지 ‘요금 체계가 바뀌어서만 생긴 차이’라고 확인한 것은 아니다.
가격이 달라도 큰 차이라는 실무 메시지는 유지된다. 모두 저장 usage의 **리스트 단가 환산**이다.

| 비교 | 공식 Standard | 기존 발표 환산 |
|---|---:|---:|
| 자동(-1) / 미지정 | **{r['actual']['auto_unspecified']:.2f}배** | **{r['legacy']['auto_unspecified']:.2f}배** |
| 자동(-1) / 명시적 0 | **{r['actual']['auto_zero']:.2f}배** | {r['legacy']['auto_zero']:.2f}배 |

| 조건 | n | 사고 평균 | 응답 평균 | Standard $/호출 | ±$0.05 통과 | 정확히 $38.016 | Wilson 95% (허용오차) |
|---|---:|---:|---:|---:|---:|---:|---|
'''
    for row in sw["rows"]:
        lo, hi = row["wilson95"]
        text += f"| {row['label']} | {row['n']} | {row['mean_tokens']['thoughts']:.2f} | {row['mean_tokens']['cands']:.2f} | ${row['cost_per_call']['actual']:.8f} | {row['pass_tolerance_0_05']}/{row['n']} | {row['exact_1e_9']}/{row['n']} | {lo*100:.1f}–{hi*100:.1f}% |\n"
    lo, hi = r["actual"]["auto_unspecified_ci95"]
    text += f'''
**권장 발표 문구**

> 간단한 계산 한 문제에서 미지정과 자동 조건은 ±$0.05 허용오차 기준 각각 6/6이었다.
> 비용은 공식 Standard 단가로 약 {r['actual']['auto_unspecified']:.0f}배, 기존 발표의 환산 단가로 약 {r['legacy']['auto_unspecified']:.0f}배 차이였다.

주의:

1. 미지정과 명시적 `0`은 서로 다른 조건이다. 후자는 **5/6**이며 10배 자릿수 오류 1회가 있다.
2. 질문은 **exact**를 요구했다. 느슨한 허용오차가 `37.9944`도 통과시키므로 정확한 숫자 채점도 병기한다.
   정확한 수치 기준 자동은 3/6이다. 허용오차 통과 횟수를 ‘답이 똑같다’ 또는 ‘정확도 동등’으로 말하지 않는다.
3. 비용 배수의 독립 재표집 bootstrap 95% 구간은 Standard 자동/미지정 **[{lo:.2f}, {hi:.2f}]배**
   (20,000회, seed=42). 한 문제 반복의 조건부 불확실성이며 다른 문제로의 일반화 구간은 아니다.
4. 512 조건은 모두 `STOP`, 사고량 **127–154**였다. 오답 원인을 ‘사고가 예산에 잘림’이라고 확인하지 않았다.
5. 사고가 발생한 행의 **토큰 합계 기준** 사고 비중은 **{sw['thought_share_aggregate']*100:.3f}%**.
   조건별/행별 비율의 단순 평균과 혼용하지 않는다.
6. 미지정에서 사고 0이 관측되었다는 사실만으로 모든 시점·모델의 기본값을 확정하지 않는다.
   현재 공식 Gemini 3 문서는 `thinkingLevel`을 사용하며 Flash-Lite의 `minimal`도 완전 off를 보장하지 않는다.
   기존 `thinkingBudget` 로그는 역사적 관측으로 보존한다. 새 기본 비교는 exp10을 사용하고,
   과거 예산 요청 재시도는 `--allow-legacy-budget`로 명시해야 한다. 지원/효과는 재확인이 필요하다.

```bash
python tools/thinking_sweep.py --summarize results/thinking_sweep.jsonl
```

## 2. 언어 비교 80행 — 호출당과 문자당 지표를 함께 보고

설명 과제 1개와 추론 과제 1개를 각각 EN/KO로 20회씩 실행했다. 80/80이 `STOP`이다.
다양한 과제 80개가 아니다. 원자료에는 응답 본문·정답 라벨·실제 사고 언어가 없다.
따라서 의미량, 정확도, 추론 깊이를 이 로그만으로 재채점할 수 없다.

### 공식 Standard 단가

| 과제 | EN $/호출 | KO $/호출 | KO/EN | EN $/1,000자 | KO $/1,000자 | KO/EN |
|---|---:|---:|---:|---:|---:|---:|
'''
    for task in ("explain", "reason"):
        m=e["language"]["actual"][task]["metrics"]
        a,b=m["per_call"],m["per_1000_chars"]
        text += f"| {task} | {a['en']:.8f} | {a['ko']:.8f} | {a['ratio_ko_en']:.3f} | {b['en']:.7f} | {b['ko']:.7f} | {b['ratio_ko_en']:.3f} |\n"
    text += '''
reason에서 한국어 호출이 저렴하면서 한국어 문자당 비용은 더 높을 수 있다. 둘은 다른 질문의 답이다.
‘싸 보이는 착시’나 ‘한국어가 일을 덜 함’으로 바꾸어 해석하지 않는다.
글자당 지표는 **동일 의미량 비교가 아니다.** 추론형의 EN 사고 평균 1,616과 KO 1,116도
소비 토큰 수 차이이지 영어가 더 깊게 생각했다는 자체 측정은 아니다.

### Welch 교정 — 단가 효과와 통계 구현 효과를 분리

아래 표는 **기존 $1.25/$10 환산 단가를 고정**하고 분포 계산만 고친 것이다.
정규근사는 수치적으로 안정적인 `2*norm.sf(abs(t))`로 재계산했다.
원래 `1-CDF` 구현은 explain 문자당 p를 0으로 반올림했다.

| 과제 / 지표 | t | 자유도 | 정규근사 p | 올바른 Welch p | Bonferroni(4) p |
|---|---:|---:|---:|---:|---:|
'''
    for task in ("explain", "reason"):
        for key,label in (("per_call","호출당"),("per_1000_chars","문자당")):
            x=e["language"]["legacy"][task]["metrics"][key]
            text += f"| {task} / {label} | {x['welch_t']:.3f} | {x['df']:.3f} | {x['normal_approx_p']:.2e} | **{x['p']:.2e}** | {x['bonferroni_4_p']:.2e} |\n"
    text += '''
네 비교는 교정 후에도 5% 기준에서 유의하다. 유의성의 유지와 p값 구현의 정확성은 별개다.
공식 단가로 바꾸면 입력/출력 가중치도 변하므로 p값이 조금 달라진다. 공식 단가 출력은
`results/stats_thinking.txt`, 기존 단가의 교정 출력은 `results/stats_thinking_legacy.txt`다.

```bash
python tools/stats_test.py results/live_lang_thinking.jsonl
python tools/stats_test.py results/live_lang_thinking.jsonl --price-basis legacy
```

가정과 한계: Welch는 독립 관측을 가정한다. 호출 순서·시점 효과와 반복 호출 간 의존을 완전히 통제한
무작위 언어 실험은 아니다. 유의성은 이 조건의 비용 지표에 대한 것이며, 언어 일반 성능이나 정확도 동등성 검정이 아니다.

## 3. 새 로컬 실측 — FLORES-200 대응 번역문 전체

2026-09-20에 공개 FLORES-200 devtest의 영어/한국어 **1,012쌍 전부**를 다시 인코딩했다.
문장별 개행만 제거하고 나머지 텍스트는 바꾸지 않았다. 아래는 **토큰 합계의 비율**이다.

| 토크나이저 | EN 토큰 | KO 토큰 | KO/EN |
|---|---:|---:|---:|
'''
    for name,x in e["flores"]["tokenizers"].items():
        text += f"| `{name}` | {x['en']:,} | {x['ko']:,} | **{x['ko_en_ratio']:.4f}배** |\n"
    text += f'''
문자 합계는 EN **{e['flores']['chars']['en']:,}**, KO **{e['flores']['chars']['ko']:,}**,
KO/EN **{e['flores']['ko_en_char_ratio']*100:.2f}%**였다. 대응 번역문이어도 한국어 글자 수는 절반 수준이다.
이 결과는 ‘대응 내용에 한국어가 더 많은 토큰을 쓰는 경향’을 지지한다.
하지만 상용 모델의 생성 usage·추론 정확도·모든 도메인의 배수를 측정한 것은 아니다.

원자료·라이선스: `data/flores200/README.md` (NLLB Team et al., CC-BY-SA 4.0).
문장별 계측은 `results/flores_tokenizers.jsonl`, 파일 SHA-256·버전은 `results/flores_tokenizers.json`.

```bash
python tools/parallel_tokenizer_bench.py
```

추론 정확도의 외부 근거: [Language Matters, 표 1](https://arxiv.org/html/2505.17407v1#S4.T1)에서
한국어 MATH-500 입력에 영어/한국어 prefilling을 적용한 네 모델 평균은 **83.7% / 75.4%**다.
이는 외부 연구의 결과이며 이번 저장소에서 모델을 실행해 재현한 정확도가 아니다.
영어 우위의 범위와 모델 차이를 유지해서 인용한다.

## 4. 과거 예비 기록과 누락 원자료

기존 37.5배 단발 예비측정, 폴백 모델이 섞인 N=5, 미지정 N=100 결과는
[수정 전 기록](docs/archive/LIVE_RESULTS_original.md)에 보존했다.
그 원자료는 현재 저장소에 없으므로 **이번에 재검증된 실측으로 소개하지 않는다.**
새 코퍼스 측정이나 mock 응답으로 누락된 live 원자료를 대신 만들지 않았다.
새 유료 실행은 다른 파일에 저장하고, 재현이 원래 숫자와 같을 것이라고 보장하지 않는다.

전체 변경: [정정 보고서](docs/CORRECTIONS.md) · 기계 판독 지표: `results/audit_metrics.json`.
'''
    return text


def corrections_report(e):
    p=e["language"]["legacy"]["reason"]["metrics"]["per_1000_chars"]
    sc=e["scenarios"]
    return f'''# 정정 보고서 — 주장은 유지하고 수치·증거·구현을 맞추기

기준 커밋: `ef4cde1` (원격 main 확인본) · 정정일 **2026-09-20**.
새 유료 API 호출 **0회**. 원래 API 로그 110행은 보존했으며, 로컬 토크나이저와 소프트웨어 검증만 새로 실행했다.
이 문서는 `tools/render_reports.py`와 원자료에서 생성된다.

## 1. 무엇을 유지하는가

**영어 활용, KISS/DRY/YAGNI, 불필요한 설명·사고 최소화, 결정적인 스펙 선주입, 캐싱·컨텍스트 관리**라는
실무 주장을 유지한다. 오류는 메시지 전체가 아니라 어떤 지표로 무엇을 증명했다고 말했는지,
비교 조건, 단가, 통계 구현, 시나리오를 실측으로 부른 부분에 있었다.

- **한국어 비용 경향:** FLORES-200 1,012쌍을 직접 다시 인코딩해 1.4723배 / 2.3669배를 재현했다.
- **영어 추론의 이점:** 외부 정확도 연구로 보강한다. 사고 토큰 수를 ‘추론 깊이’로 정의하지 않는다.
- **240배:** 삭제하지 않는다. 기존 발표 환산으로 240.02배, 실제 모델 Standard로 199.47배라고 병기한다.
- **시나리오:** 가치가 없다는 뜻이 아니다. ‘가정을 넣으면 이만큼’과 ‘정책을 적용해 실제 이만큼’을 분리한다.

자세한 표와 재현 명령은 [LIVE_RESULTS.md](../LIVE_RESULTS.md)에 있다.
격리·폐기했던 주장을 원자료로 되돌려 다시 쓸 수 있는지 판정한 표는 [REASSERTED.md](REASSERTED.md)에 있다.
정정 과정에서 문구가 사라진 주장의 목록과 재주장 조건은 [RETIRED.md](RETIRED.md)에 있다.

## 2. 왜 Welch의 p값을 고쳐야 하나

각 언어의 평균 차이를 그 차이의 추정 표준오차로 나눈 값이 t다. 각 표본 수가 20이라고 해서
정규분포로 바꾸어도 된다는 보장은 없다. 두 집단 분산이 다르면 유효 자유도는 약 20–36까지 내려간다.

```text
a = s_KO² / n_KO,  b = s_EN² / n_EN
t = (mean_KO - mean_EN) / sqrt(a + b)
df = (a + b)² / (a²/(n_KO-1) + b²/(n_EN-1))
p = 2 * StudentT.sf(abs(t), df)
```

reason 문자당 비용(기존 가격 고정)은 t={p['welch_t']:.3f}, df={p['df']:.3f}다.
정규근사의 **{p['normal_approx_p']:.2e}**와 달리 Welch p는 **{p['p']:.2e}**, 약
**{p['p']/p['normal_approx_p']:.0f}배** 크다. t분포의 두꺼운 꼬리가 평균·분산 추정의 불확실성을 반영하기 때문이다.

**네 비교 모두 유의성은 남는다.** 네 비교의 Bonferroni 보정 후에도 마찬가지다.
따라서 정정은 ‘언어 비용 차이가 사라졌다’가 아니라 **‘그 차이에 붙인 p값이 잘못됐다’**다.
이 검정은 정확도나 동일 의미량을 검증한 것이 아니다.

`1-CDF` 방식은 CDF가 1로 반올림될 때 p=0을 만든다. `sf`를 써서 피한다.
SciPy `ttest_ind(equal_var=False)`와 독립 대조하는 회귀 테스트를 추가했다.
상수 표본/표본 부족은 검정 불가(nan)로 처리하며 유의하다고 만들지 않는다.

## 3. 240배의 정확한 조건

- 비교는 **자동 / 미지정**이다. 명시적 0과 섞지 않는다.
- ±$0.05 통과: 미지정 6/6, 0은 5/6, 자동 6/6.
- 정확한 숫자 채점: 미지정 6/6, 0은 5/6, 자동 3/6. `37.9944`는 정확한 $38.016과 다르다.
- 관측 통과 횟수가 같은 것을 모집단 정확도 동등성으로 일반화하지 않는다.
- 공식 단가의 자동/0은 195.97배. 과거 약 149배는 잘못 연결된 $0.10/$0.40 가격으로 나온 값이었다.
- ‘512는 사고가 잘려서 오답’이라는 원인은 철회한다. 해당 로그는 STOP, 사고 127–154 토큰이다.
- 단가를 바꾼 환산치와 당시 실제 청구금액을 구분한다. 240과 199의 차이를 단순한 가격 변경 이력으로 단정하지 않는다.

## 4. 시나리오 수치는 어떻게 보존했나

| 항목 | 정정 후 상태 | 재현 |
|---|---|---|
| 페르소나 20.8배 | `legacy`에서 유지. 한국어 hidden 사고 1.44·effort 0.35·출력 확대 2.9·턴 6/2·최소 길이 무시 캐싱을 가정 | `python demo/compare_personas.py --scenario legacy` |
| 수정 페르소나 | **{sc['personas']['current']['ratio']:.1f}배**. 기본 사고 언어 승수 1.0, 캐시 최소 길이 적용. 여전히 비용 모형 | `python demo/compare_personas.py` |
| SDD 약 71% | 예열된 캐시의 기존 가정으로 **{sc['sdd']['legacy_warm']['saving_pct']:.3f}%**. 스펙 작성 토큰 비용은 원래부터 포함 | `python experiments/exp04_agent_loop_sdd.py --warm-cache` |
| 기본 SDD | 사이클별 cold-cache 첫 쓰기 포함 **{sc['sdd']['cold']['saving_pct']:.3f}%**. 40→12턴은 여전히 가정 | `python experiments/exp04_agent_loop_sdd.py` |
| 사다리 3.06배 | 과거 고정 발화 재생의 가정값으로 역사 기록에 보존. 실제 정책 A/B 절감 실측으로 인용하지 않음. 현재 규칙으로 다시 재생하면 2.81배 | `presentation/archive/ladder_lean.md` · `analysis/lean_vs_full.py` |
| 카페 -8.3% | 고정 usage 추정치와 GPT-5 단가에서 산술 유지. 백지 스펙 작성·재작업 감소의 인과 효과 아님 | `demo/vibe_vs_spec/sensitivity.py` |
| 압축+캐시 | 원문 캐시 **$0.4014**, 절반 압축+캐시 **$0.2007**. 압축 자체 비용·품질은 별도 | `experiments/exp09_dry.py` |
| 누적 절감 | **{sc['stack_saving_pct']:.3f}%** 산술 유지. 60–80%에 포함된다는 표현과 검증된 상한 표현 제거 | `experiments/exp06_other_levers.py` |
| subagent -87% | 메인만 센 과거 모형으로 명시. 기본은 같은 매턴 툴 작업량에서 자식·요약·compaction까지 계상 | `experiments/exp11_tool_output_bloat.py` |

카페의 cache 312/468도 실제 캐시 적격성을 확인한 관측값이 아니다.
전부 신규 입력으로 계산한 GPT-5 대안은 $0.0716975 → $0.0659250 (약 -8.1%)다.
-8.3%는 원래 추정 캐시 가정의 산술로 유지한다. 어느 쪽도 실제 SDD 정책 효과 실측이 아니다.

페르소나 시나리오의 `A_THINK`, `B_THINK`는 실제 hidden 사고 계측이 아니다.
다른 과제의 관측 범위를 참고했다는 이유만으로 새 작업의 실측값이 되지 않는다.
기존 300 토큰 수정 가정은 ‘898–3,049 범위 안’도 아니었고, 1.44 승수 후 상한을 넘기도 했다.
`legacy`는 이런 **가정의 이력 재현**이며 유효한 현재 캐시 정책 추천이 아니다.

캘리브레이션도 변경했다. 입력 79,130을 같은 자료로 역산하면 g=4,707.733…,
반올림 g=4,700일 때 입력 합 79,014(오차 0.147%). Sonnet $3/$15, 사고 19,440,
기존 전체 입력 cache-write 1.25 가정을 모두 포함하면 비용 $1.0356975 대 $1.0361325,
오차 **0.042%**다. 이는 **동일 자료 내부 정합**일 뿐 독립 예측력 검증이 아니다.
과거 코드의 61.7%와 문서의 수동 5.8%를 현행 검증 결과로 쓰지 않는다.

## 5. 실행 결함과 거짓 통과 수정

| 문제 | 실제 수정 | 회귀 검사 |
|---|---|---|
| 발표 검증이 상수만 확인 | primary evidence로 만든 모든 슬라이드 텍스트·조건·장수·텍스트 박스 경계를 실제 PPTX와 대조 | 240→999 변조 거부; 누락 파일은 실패 |
| PDF/대본과 덱이 다름 | PPTX 5종·대본을 한 생성 원천으로 통합. 실제 PDF 텍스트/쪽수도 검사 | `verify_deck.py --with-pdf` |
| 실패 assertion이 exit 0 | `test_intent_guard.py`, `test_orchestrator.py`에 실패 종료 연결 | 강제 실패 삽입 후 exit 1 |
| 셸 파이프가 실패를 가림 | `verify_all.sh`에 pipefail; SKIP을 전체 통과로 출력하지 않음 | 셸 설정·하위 실패 회귀 |
| AC가 문자열만 검사 | 메모 저장/새로고침/선택/삭제, 카페 반응형/앵커를 Chromium에서 실행 | 무동작 메모·모바일 2열 변조 거부 |
| 작업 간 상태 누출 | task_id별 의도 추적기; 초기화 전 inner는 명시적 오류 | 새 작업·동일 문구·교차 작업 테스트 |
| 비용 계산 불일치 | `decision_cost`에 범위·reset·출력 상한·diagnose/apply 통합 | 같은 tier-up이 두 경로 모두 $0.05875 |
| 입력 증가분 이중 계상 | g는 출력을 포함한 총 증가분. `g + output`이 아닌 g만 누적 | 1,419→6,119→10,819 |
| 부수 단어가 작업 목적 선점 | 설계·구현·설명 우선; TOOL 단어 축소 | 구성 반례. 실제 라우터 오류율은 미측정 |
| exp10 실패에도 ‘확인됨’ | raw 관측/완료/실패/정답 필드 연결, 반복수 n, 모델 ID·가격 연결 | 전부 실패/일부 절단 시 성공 판정 금지 |
| exp11 Content 구조 오류 | role+parts 사용, 원래 모델 Content 통째로 전달 | thoughtSignature·functionCall id 보존 |
| exp11 캐시 두 번 차감 | 전체 prompt와 cached를 cost에 전달, 한 번만 차감 | mock $0.00178 (잘못된 $0.00098 거부) |
| 툴 첫 입력을 재입력으로 오인 | 첫 요청=툴 요구, 둘째=툴 본문 첫 입력, 셋째=이력 재전송 | 3요청 payload 검증 |
| 캐시 최소 길이 공통 1K | 모델별 조건을 pricing에 모음. 미확인은 할인 가정 금지 | Haiku 4.5: 4,095/4,096 경계 |
| 경로 27개가 비 UTF-8 | ASCII 경로로 정규화, 파일·참조·기본 검증 경로 수정 | `docs/path_migration.json`, 경로 UTF-8 검사 |
| CI 파일이 없는데 README에는 있음 | 실제 GitHub Actions 추가; 무과금 재계산·회귀·브라우저·덱 검사 | `.github/workflows/ci.yml` |
| 케이스 덱에서 스크린샷·표가 사라짐 | 생성기 단일 원천으로 재구성하며 그림·표를 그리지 않았다. 슬라이드 3장(첫 화면·모바일 390px·전체 페이지 축소)과 표 3개(토큰·단가·손익분기)를 생성기에 넣고, 원본 PNG를 **바이트 동일**하게 삽입 | `test_case_deck_restored_figures_are_byte_identical_to_sources` · `test_case_deck_fact_tables_match_usage_and_price_sources` · PDF 그림 배치 검사(3·4·5쪽) |

Browser/mock 검증은 **소프트웨어 실동작/계약 테스트**다. 모델 품질이나 API 청구의 새 실측으로 세지 않는다.
모든 오류가 없음을 수학적으로 보장한 것이 아니라, 지적된 실패 유형을 재현 가능한 검사로 막은 것이다.

## 6. 문헌과 과거 문서의 정리

- *Language Matters*의 83.7%/75.4%는 한국어 MATH-500, 네 모델 평균, prefilling 비교다.
  상용 모델 전체나 ‘토큰이 길어서 더 깊다’의 근거로 확대하지 않는다.
- Spec-Kit +97~109%는 **OpenSpec 대비** 블로그 두 사례다. ‘SDD 대 무스펙’ 실험이 아니다.
- ETH 연구는 **저장소 컨텍스트 파일** 조건이다. 사람이 짧게 쓰기만 하면 항상 이득이라는 결론은 아니다.
- 초기 파일의 N=5/N=100과 37.5배 원자료는 현재 미포함. 당시 서술은
  `docs/archive/`에 보존하되 재검증된 결과에서 제외했다.
- 옛 사다리 작업 노트는 `presentation/archive/`에 비현행으로 격리했다.
  최신 덱/대본은 동일 원천에서 재생성한다. ‘발표 브랜치를 main에 합치지 말라’는 오래된 안내도 제거했다.
- 요금표의 모호한 GPT-5.x를 실제 `gpt-5`에 연결했고, DeepSeek은 현행 peak/off-peak 조건을 분리했다.
  표의 범위를 넘어서는 모델·장문·특수 서비스 단가는 자동 추측하지 않는다.

## 7. 재현과 남은 검증 범위

```bash
pip install -r requirements-dev.txt
python -m playwright install --with-deps chromium
python tools/reproduce_audit.py --with-pdf
python -m pytest -q
python run_all.py                       # --live 없음: 유료 호출 0
python demo/vibe_vs_spec/verify_ac.py    # static + browser; 브라우저 없으면 실패
python tools/verify_deck.py --with-pdf
```

PDF 재생성에는 LibreOffice와 Nanum 폰트가 필요하다:
`python presentation/deckgen/make_pdf.py --check`.
`python tools/check_audit.py`는 로컬 전체 게이트를 실행하고
현재 테스트 실행 결과를 `results/verification.json`에 별도로 기록한다. 검증 수를 본문에 고정해 놓지 않는다.

**이번에 하지 않은 것:** 새 유료 LLM 호출, 다양한 문제의 한/영 정확도 재현, 실제 정책 A/B,
블라인드 품질 동등성 검정, 실제 IDE GUI와 발표장 기기 수동 시험, 실제 청구서 대조.
이 영역은 미실행/미검증으로 남긴다. ‘전부 실측’이라는 이름을 얻으려고 시나리오를 관측값으로 바꾸지 않는다.
'''


def reassertion_report(e):
    """격리·폐기했던 주장을 원자료로 다시 계산해 '다시 쓸 수 있는 문장'을 판정한다.

    값은 원자료/스크립트 재현값에서 가져온다. 손으로 적은 숫자는 tests/test_docs_consistency.py가
    실제 스크립트 출력과 대조한다.
    """
    import json
    fl = e["flores"]["tokenizers"]
    sc = e["scenarios"]
    sweep = {r["label"]: r for r in e["thinking_sweep"]["rows"]}
    auto = sweep["자동 (-1)"]["ratio_to_unspecified"]
    ts = e["thinking_sweep"]["thought_share_aggregate"]
    p = sc["personas"]
    sdd = sc["sdd"]
    cc = sc["compression_cache"]
    tb = sc["tool_bloat"]
    cache = sc["cache"]
    results_current = json.loads((ROOT / "demo/results_current.json").read_text(encoding="utf-8"))
    results_legacy = json.loads((ROOT / "demo/results.json").read_text(encoding="utf-8"))
    return f'''# 격리한 주장 재확인 — 다시 주장할 수 있는가

확인일 **2026-09-20** · 새 유료 API 호출 **0회**. 격리하거나 폐기했던 주장을 원자료·스크립트로 다시 계산했다.
[docs/CORRECTIONS.md](CORRECTIONS.md)가 “무엇이 틀렸는가”라면, 이 문서는 **“그래서 무엇을 다시 말할 수 있는가”**다.

**결론: 절감 주장은 조건을 붙이면 전부 다시 쓸 수 있다.** 다시 쓰지 않는 것은 격리 사유가
값이 아니라 **원자료 없음·미측정**인 항목뿐이다(§3). 값은 반드시 재현값으로 쓰고, 손으로 옮겨 적지 않는다.

## 1. 다시 쓸 수 있는 절감 문장

| # | 다시 쓸 문장 | 재확인 값 | 근거 유형 | 재현 |
|---|---|---|---|---|
| 1 | 같은 저장 발화를 두 정책으로 처리하면 3칸 사다리 쪽 지출이 **2.81배** 낮다 | 7칸 $0.4168 → 3칸 $0.1485 | 정책 지출 재생(가정) | `python analysis/lean_vs_full.py` |
| 2 | 짧은 리워크에서도 이득: **1턴 27%, 2턴 43%** | $0.0594→$0.0434 · $0.0979→$0.0560 | 위와 동일 | 위와 동일 |
| 3 | 실패가 반복될수록 벌어진다: 3회 1.28배 → 6회 **2.80배** (역전 구간 없음) | 누적 반영 후 | 위와 동일 | 위와 동일 |
| 4 | 캐시 100% 적중이면 **{cache['saving_pct']:.1f}%** 절감, 배치를 틀리면 오히려 **{cache['all_miss_usd']/cache['no_cache_usd']*100-100:+.1f}%** | $8.55 → $3.219 / 잘못 배치 $10.05 | 비용 시나리오 | `python experiments/exp03_prompt_caching.py` |
| 5 | 절반 압축 + 캐싱 병용 **{100-cc['both']/cc['plain']*100:.1f}%** (캐싱만 {100-cc['cached']/cc['plain']*100:.1f}%) | 원문 ${cc['plain']:.2f} → 캐시 ${cc['cached']:.4f} → 병용 ${cc['both']:.4f} | 비용 시나리오(압축 비용·품질 별도) | `python experiments/exp09_dry.py` |
| 6 | 같은 예문에서 설명만 줄여 토큰 **83%** 감소 | 342 → 58 토큰 | 로컬 인코딩 실측(예문 한정) | `python experiments/exp05_verbosity_effort.py` |
| 7 | 결정을 스펙으로 주입하면 입력 3배에도 총비용 **66%** 감소 | $0.0630 기준 | 비용 시나리오 | `python experiments/exp02_output_to_input.py` |
| 8 | SDD 비용 시나리오 **{sdd['cold']['saving_pct']:.1f}%** (예열 캐시 가정 {sdd['legacy_warm']['saving_pct']:.1f}%) | 턴 40→12 가정 포함 | 비용 시나리오 | `python experiments/exp04_agent_loop_sdd.py` |
| 9 | 페르소나 시나리오 **{p['current']['ratio']:.1f}배** = 연 ${results_current['year_gap']} (기존 가정 {p['legacy']['ratio']:.1f}배 · 연 ${results_legacy['year_gap']}) | A ${p['current']['a_usd']:.4f} / B ${p['current']['b_usd']:.4f} | 가정 시나리오 | `python demo/compare_personas.py` |
| 10 | 카페 케이스 **-8.3%** (Sonnet -7.6%, 캐시 없이 -8.1%) | 고정 usage 산술 | 추정 usage의 산술 | `python demo/vibe_vs_spec/sensitivity.py` |
| 11 | 전체 시스템 기준 subagent **{100-tb['subagent']['whole_system_usd']/tb['naive']['whole_system_usd']*100:.1f}%**, 컴팩션 {100-tb['compact']['whole_system_usd']/tb['naive']['whole_system_usd']*100:.1f}% | ${tb['naive']['whole_system_usd']:.3f} → ${tb['subagent']['whole_system_usd']:.3f} / ${tb['compact']['whole_system_usd']:.4f} | 비용 시나리오(자식·요약 포함) | `python experiments/exp11_tool_output_bloat.py` |
| 12 | 레버 적층 시나리오 **{sc['stack_saving_pct']:.1f}%** | 잔여 14% | 순차 가정 산술 | `python experiments/exp06_other_levers.py` |
| 13 | 같은 내용이면 한국어 출력 토큰이 **{fl['o200k_base']['ko_en_ratio']:.4f}배**(o200k) · **{fl['cl100k_base']['ko_en_ratio']:.4f}배**(cl100k) | FLORES-200 1,012쌍 실측 | 로컬 토크나이저 실측 | `python tools/parallel_tokenizer_bench.py` |
| 14 | 사고 예산을 미지정하면 같은 답에 **{auto['actual']:.2f}배**(공식 단가) · **{auto['legacy']:.2f}배**(기존 환산) 지출 | $0.000028 → $0.00558525 | 저장 API 로그 재계산 | `python tools/thinking_sweep.py --summarize results/thinking_sweep.jsonl` |
| 15 | 사고가 난 호출에서 사고 토큰이 출력 토큰의 **{ts*100:.2f}%** | 사고 127–3,704토큰 범위 | 저장 API 로그 재계산 | 위와 동일 |

1·2·3은 정책 **지출 모형**이다. 완료 작업당 절감률도, 품질 동등성도 아니다.
4~12는 토큰·단가·턴 가정 위의 계산이다. 13~15만 이 저장소가 직접 만든 실측·로그 재계산이다.
모든 문장에 “~라는 가정에서”를 붙여 말한다.

## 2. 근거를 새로 붙인 것 (격리 해제)

| 격리했던 근거 | 문제였던 점 | 새 근거 |
|---|---|---|
| “37.5배”(단발 측정) | 그 회차 원자료가 저장소에 없음 | 저장 로그 30행 n=6 재계산 → **{auto['actual']:.2f}배** · **{auto['legacy']:.2f}배** (부트스트랩 95% [{e['thinking_sweep']['ratios']['actual']['auto_unspecified_ci95'][0]:.2f}, {e['thinking_sweep']['ratios']['actual']['auto_unspecified_ci95'][1]:.2f}]) |
| “한국어가 비싸다”(N=5, 모델 혼합) | 표본 5·폴백 혼합·원자료 미포함 | FLORES-200 1,012쌍 인코딩 실측(해시 고정) + 저장 로그 80행(n=20/언어/과제) |
| 정규근사 p값 | 구현 오류(1−CDF) | Welch 교정 후에도 네 비교 유의(1.6e-3 ~ 4.0e-7) |
| “사다리 3.06배” | 옛 규칙·조건이 달랐음 | 현재 규칙 재생 2.81배(§1-1). 3.06배는 역사 기록으로만 |
| “AC 16/16 PASS” | 문자열 검사가 동작을 보증하지 않음 | Chromium 실동작 AC + 변조 거부 회귀 |

## 3. 다시 쓰지 않는 것 (원자료 없음·미측정)

| 항목 | 이유 | 대신 쓰는 것 |
|---|---|---|
| “37.5배” 자체 | 해당 회차 원자료 미포함 | §1-14의 저장 로그 값 |
| “한국어 +19.6%”(N=5), N=100 결과 | 원자료 미포함·모델 혼합 | FLORES 실측 + 80행 로그 |
| “B 트리거 0/5 → 4/5 고쳐졌다” | 실로그 재생에서 에스컬레이션 3/5, 분류 2/5=40% | “실로그 6턴 중 3회 에스컬레이션(가정 없음, 재생)” |
| “사다리 12배 절감” | 대조군을 최상위 모델로 잡을 때만 성립 | §1-1·2의 2.81배 / 1턴 27% |
| “사고 토큰 = 더 깊은 추론” | 증거가 아님 | §1-15 “사고 토큰은 요금에 붙는다” |
| “AC 통과 = 품질 보증” | 실로그 산출물에서 문구 5건 소실 | 브라우저 동작 검사 결과 |
| exp07·exp10 live “확인됨” | 미실행(키 없음) | dry-run 구조 출력만 |
| 캐시 히트율 61.7% / 5.8% | 가정값 | 히트율을 명시한 시나리오(§1-4) |
| 라우터 오류율·검출률 | 미측정 | “오류율 미측정” 표기 유지 |

## 4. 발표용 문장 형식

> “정책 A는 (가정 X에서) 정책 B보다 N배 낮은 지출을 보였다. N은 저장 발화·토큰 가정의 재생값이며,
> 품질 동등성과 완료 작업당 절감률은 검증하지 않았다.”

숫자는 이 문서의 값(스크립트 재현값)을 쓰고, 발표 자료의 수치와 다르면 발표 자료를 다시 생성한다.
'''


def write_reports(e):
    (ROOT / "LIVE_RESULTS.md").write_text(live_report(e), encoding="utf-8")
    (ROOT / "docs/CORRECTIONS.md").write_text(corrections_report(e), encoding="utf-8")
    (ROOT / "docs/REASSERTED.md").write_text(reassertion_report(e), encoding="utf-8")


if __name__ == "__main__":
    write_reports(build())
