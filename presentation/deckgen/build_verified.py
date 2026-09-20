#!/usr/bin/env python3
"""Canonical slides + speaker scripts, generated from primary logs and scenarios.

No hard-coded PASS counts. Numerical claims come from lab.evidence.build().
The validator compares every slide's text to these regenerated specifications,
not a handful of constants or a permissive 'contains 240' test.
"""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lab.evidence import build


def slide(title, hero, lines, scope, source, images=None, facts=None):
    """images: [(저장소 상대 경로, 캡션)] / facts: [(항목, 값)] — 둘 다 덱에 그대로 그려진다."""
    return dict(title=title, hero=hero, lines=lines, scope=scope, source=source,
                images=images or [], facts=facts or [])


def specifications(e):
    f = e["flores"]["tokenizers"]
    sw = e["thinking_sweep"]
    ratios = sw["ratios"]
    lang = e["language"]
    scen = e["scenarios"]
    p = lang["legacy"]["reason"]["metrics"]["per_1000_chars"]
    case = e["estimated_case_price_sensitivity"]["models"]["gpt5"]
    corpus = "tools/parallel_tokenizer_bench.py · FLORES-200 devtest · NLLB Team (2022)"
    logs = "results/live_lang_thinking.jsonl (80 rows) · tools/stats_test.py"
    sweep_src = "results/thinking_sweep.jsonl (30 rows) · tools/thinking_sweep.py"
    A = [
      slide("시키지도 않은 시공비 청구서", "주장은 유지. 근거는 정확하게.", ["영어 활용 · KISS/DRY/YAGNI · 설명 최소화 · 결정된 스펙 주입", "불필요한 출력·사고·재전송을 줄이면 비용을 낮출 수 있다.", "이 자료는 실측, 로그 재계산, 비용 시나리오를 구분한다."], "2026-09-20 정정판", "github.com/giyeop-cody/token-cost-lab · docs/CORRECTIONS.md"),
      slide("숫자마다 증거의 종류를 붙인다", "측정 ≠ 가정 ≠ 인과 효과", ["API 저장 로그: 80건 언어 비교 + 30건 사고 예산 스윕", "새 로컬 실측: 대응 번역문 1,012쌍의 토크나이저 인코딩", "브라우저·mock: 코드 동작 검증 / 비용 시나리오: 정책 효과 실측 아님", "이번 정정의 새 유료 API 호출은 0회다."], "검증 범위", "results/audit_metrics.json · tests/"),
      slide("요금은 모델 ID와 단가를 함께 본다", "$0.25 / $1.50", ["Gemini 3.1 Flash-Lite · Standard text · USD / 1M tokens", "출력에는 thoughtsTokenCount + candidatesTokenCount를 포함한다.", "기존 $1.25/$10은 발표 환산 가정으로 보존한다. Flash-Lite 공식 과거 가격이라는 뜻은 아니다.", "usage × 리스트 단가는 청구서가 아니다. 무료 티어·계약·세금·도구료는 별도."], "공식 가격 확인: 2026-09-20", "ai.google.dev/gemini-api/docs/pricing · lab/pricing.py"),
      slide("대응 번역문에서는 한국어 토큰이 더 많다", f"{f['o200k_base']['ko_en_ratio']:.4f}× / {f['cl100k_base']['ko_en_ratio']:.4f}×", [f"o200k_base: EN {f['o200k_base']['en']:,} → KO {f['o200k_base']['ko']:,}", f"cl100k_base: EN {f['cl100k_base']['en']:,} → KO {f['cl100k_base']['ko']:,}", "FLORES-200 devtest의 대응 번역 1,012쌍 전부를 문장별 인코딩, 토큰 합계의 비율.", "동일 단가에서의 토큰 비용 이점을 지지한다. Gemini·Claude 배수로 옮기지 않는다."], "새 로컬 토크나이저 실측", corpus),
      slide("짧은 한국어가 적은 의미를 뜻하지 않는다", f"한국어 글자 수 = 영어의 {e['flores']['ko_en_char_ratio']*100:.2f}%", ["대응 번역문인데 한국어 문자는 약 절반이다.", "$/1,000자는 문자 단위 지표이며 언어 간 의미량을 맞춘 지표가 아니다.", "‘한국어가 일을 덜 했다’는 결론은 글자 수만으로 낼 수 없다."], "문자 수 실측 / 해석 제한", corpus),
      slide("호출당 비용과 문자당 비용은 다른 질문", "둘 다 보고, 한쪽을 착시라 부르지 않는다", [f"reason / Standard: KO/EN 호출당 {lang['actual']['reason']['metrics']['per_call']['ratio_ko_en']:.3f}×", f"reason / 기존 환산: 호출당 {lang['legacy']['reason']['metrics']['per_call']['ratio_ko_en']:.3f}×, 문자당 {lang['legacy']['reason']['metrics']['per_1000_chars']['ratio_ko_en']:.2f}×", "같은 입력 과제라도 생성 내용·답의 품질·추론 언어까지 같다고 확인하지 않았다.", "실험은 과제 2개 × 언어 2개 × 20회 반복이다. 일반 언어 벤치마크가 아니다."], "저장 API usage 재계산", logs),
      slide("영어 추론의 이점은 정확도로 뒷받침한다", "83.7% vs 75.4%", ["Language Matters (2025), 표 1: 한국어 MATH-500 입력, 영어 / 한국어 prefilling", "평가한 네 모델 평균. 모델별 차이가 크며 모든 모델·도메인의 우위는 아니다.", "저장소의 사고 토큰 수가 많다는 사실만으로 ‘더 깊거나 정확하다’고 증명하지 않는다.", "영어 활용 권장은 유지하되 자기 과제의 정확도·비용으로 확인한다."], "외부 연구 결과 / 자체 재현 아님", "arxiv.org/html/2505.17407v1#S4.T1 · SOURCES.md"),
      slide("간단한 계산에도 사고가 비용을 크게 늘린다", f"약 {ratios['actual']['auto_unspecified']:.2f}배 / 기존 {ratios['legacy']['auto_unspecified']:.2f}배", ["자동(-1) / 미지정 비교. 같은 문제를 조건당 6번 실행한 저장 로그.", "±$0.05 허용오차 통과는 각각 6/6. 일반 정확도의 동등성 증명은 아니다.", f"자동 / 명시적 0은 Standard {ratios['actual']['auto_zero']:.2f}배. 명시적 0은 5/6.", "240배 메시지는 기존 환산 단가라는 조건을 붙여 유지한다."], "저장 로그 + 두 단가의 재계산", sweep_src),
      slide("미지정과 0을 합치지 않는다", "6/6 · 5/6 · 2/6 · 6/6 · 6/6", ["순서: 미지정 / 명시적 0 / 512 / 2048 / 자동(-1), ±$0.05 기준", "정확히 $38.016 기준은 각각 6/6 · 5/6 · 1/6 · 4/6 · 3/6.", "6/6의 Wilson 95% 구간도 약 61–100%다. 동등성 검정이 아니다.", "512 조건은 모두 STOP, 사고 127–154 토큰. ‘예산에 잘려 오답’이라는 원인은 미확인."], "채점 기준·표본 한계 공개", sweep_src),
      slide("Welch 검정은 t분포를 쓴다", f"t = {p['welch_t']:.3f} · 자유도 = {p['df']:.3f}", [f"reason / 문자당 / 기존 단가: 정규근사 {p['normal_approx_p']:.2e} → Welch {p['p']:.2e}", "평균 차이의 표준오차를 표본에서 추정하므로 정규분포보다 꼬리가 두꺼운 t분포를 사용.", "p = 2 × t.sf(|t|, df). 1-CDF는 작은 꼬리에서 정밀도를 잃을 수 있다.", "p값은 수정해야 한다. 유의성의 소멸을 뜻하지는 않는다."], "통계 구현 교정", "tools/stats_test.py · scipy.stats.ttest_ind(equal_var=False) 회귀 대조"),
      slide("교정 후에도 비용 차이의 유의성은 유지", "네 비교 모두 Bonferroni(4) 통과", [f"explain 호출당: p = {lang['legacy']['explain']['metrics']['per_call']['p']:.2e}", f"explain 문자당: p = {lang['legacy']['explain']['metrics']['per_1000_chars']['p']:.2e}", f"reason 호출당: p = {lang['legacy']['reason']['metrics']['per_call']['p']:.2e}", f"reason 문자당: p = {p['p']:.2e} — 모두 기존 $1.25/$10 단가. 반복 호출의 조건부 검정."], "유의성 ≠ 의미량·추론 품질 증명", logs),
      slide("네 가지 원칙은 그대로 쓴다", "필요한 결과만, 적합한 설정으로", ["① 영어는 토큰 효율과 추론 정확도에 유리할 수 있다. 사용자에게는 필요한 언어로 답한다.", "② KISS/DRY/YAGNI: 불필요한 코드·전체 재출력·재작업을 줄인다.", "③ 설명 길이와 사고 예산을 과제에 맞춘다. 정확도 게이트를 함께 둔다.", "④ 스펙에 결정을 먼저 적는다. 스펙 작성 비용과 실제 재작업 변화를 함께 잰다."], "실무 권장 / 조건부 효과", "README.md · SOURCES.md"),
      slide("DRY: 전체 파일 대신 변경분을 받는다", "5,000 → 300 토큰", ["10회 수정에서 출력만 50,000 → 3,000으로 줄인다는 가정이면 94% 절감.", "실제 패치가 적용되고 테스트를 통과해야 절감이 성립한다.", "생성 토큰 감소를 개발 시간·품질 동등성의 실측으로 바꾸어 말하지 않는다."], "비용 시나리오", "experiments/exp09_dry.py §A"),
      slide("압축과 캐싱은 대체재만이 아니다", f"${scen['compression_cache']['cached']:.4f} → ${scen['compression_cache']['both']:.4f}", ["Sonnet 단가, 프리픽스 12,000, 100회: 첫 쓰기 + 이후 99회 캐시 읽기.", "원문 캐시 $0.4014 / 절반 압축 + 캐시 $0.2007.", "압축 비용·품질·최소 길이·TTL 조건을 만족해야 한다. 요약 생성 비용은 이 표 밖이다."], "같은 가정의 2×2 비용 비교", "experiments/exp09_dry.py §B"),
      slide("출력 대신 결정된 입력에 비용을 쓴다", "단가 차이는 지렛대, 품질은 별도", ["출력 단가가 더 높으면, 짧은 출력 대신 조금 긴 입력이 유리할 수 있다.", "입력이 늘어난 만큼 출력을 실제로 줄였는지 usage로 확인한다.", "‘입력 3배·비용 66% 절감’은 exp02의 특정 토큰 가정이지 보편 실측률이 아니다."], "비용 시나리오 / exp02", "experiments/exp02_output_to_input.py"),
      slide("캐시 적격성은 모델별로 다르다", "Haiku 4.5: 최소 4,096 토큰", ["Sonnet 4.6: 1,024 / Opus 4.6: 4,096 (공식 문서 확인일 2026-09-20)", "짧은 프리픽스를 1K 공통 규칙으로 할인하지 않는다. 미확인 기준은 ‘미확인’으로 둔다.", "적격성 충족은 히트 보장이 아니다. 실제 cache usage·TTL·쓰기/저장료를 본다."], "공식 조건 + 경계값 회귀 테스트", "platform.claude.com/docs/en/build-with-claude/prompt-caching"),
      slide("캐싱의 손익은 조건으로 재현한다", f"기본 시나리오 {scen['cache']['saving_pct']:.2f}% 절감", [f"고정 20,000 + 가변 1,000, 출력 1,500, 100회, Sonnet: ${scen['cache']['no_cache_usd']:.3f} → ${scen['cache']['cache_usd']:.3f}", f"히트 0, 매번 쓰기 가정은 ${scen['cache']['all_miss_usd']:.3f}. 캐시 없음보다 비쌀 수 있다.", "‘캐싱 90%’는 캐시 읽기 단가 할인이다. 전체 세션 절감률과 다르다."], "첫 쓰기 비용 포함 시나리오", "experiments/exp03_prompt_caching.py"),
      slide("20.8배는 페르소나 시나리오로 보존", f"기존 {scen['personas']['legacy']['ratio']:.1f}배 / 수정 기본 {scen['personas']['current']['ratio']:.1f}배", ["기존: A 6턴 / B 2턴, 출력 확대 2.9배, effort 0.35, 한국어 사고 승수 1.44 등 가정.", "기본: 사고 언어 승수는 1.0, 최소 길이 미달 캐싱은 미적용.", "두 조건 모두 일부 실파일 인코딩이 포함된 비용 모형. 실제 품질 동등 A/B가 아니다.", "python demo/compare_personas.py --scenario legacy 로 기존 발표 수치 재현."], "역사적 시나리오 / 수정 시나리오", "demo/results.json · demo/results_current.json"),
      slide("SDD 절감은 ‘턴 감소’ 가정에 달린다", f"기존 {scen['sdd']['legacy_warm']['saving_pct']:.1f}% / cold-cache {scen['sdd']['cold']['saving_pct']:.1f}%", ["40턴 → 12턴은 모델의 입력 가정. 스펙이 실제 이만큼 줄였다는 관측은 없다.", "스펙 작성: 입력 3,000 + 출력 4,000 비용을 이미 포함한다.", "기존 약 71%는 캐시 예열 비용 제외. 기본은 사이클별 첫 쓰기까지 포함한다.", "주장 유지: 짧고 결정적인 스펙을 우선 시도하되 재작업·품질·총비용으로 검증한다."], "SDD 비용 시나리오", "experiments/exp04_agent_loop_sdd.py (--warm-cache = legacy)"),
      slide("카페 케이스: 절감 관측의 증거 수준", f"usage 추정치 환산 {case['delta_pct']:.1f}%", [f"고정 usage 추정치 + GPT-5 단가: ${case['vibe_usd']:.5f} → ${case['spec_usd']:.5f}", "토큰 합계 7,868 → 8,010 (+1.8%). 실제 청구 usage가 아니라 세션 추정치다.", f"캐시 적격성 미확인. 모든 추정 입력을 신규 입력으로 환산하면 {case['no_cache_delta_pct']:.1f}%.", "Spec은 Vibe 결과를 역산. 백지 스펙 비용·재작업 감소·품질 동등성을 검증한 것은 아니다."], "추정 usage의 비용 재계산", "demo/vibe_vs_spec/usage.json · verify_ac.py"),
      slide("반례의 비교 대상을 정확히 읽는다", "SDD 도구 간 비교 ≠ SDD 대 무스펙", ["Spec-Kit +97~109%: OpenSpec 대비 두 사례의 외부 블로그 보고. 둘 다 SDD 접근.", "ETH AGENTS.md 연구: 저장소 컨텍스트 파일 조건. 모든 짧은 스펙이 손해라는 실험 아님.", "짧고 필요한 요구사항만 쓰라는 실무 원칙은 유지하되 효과를 직접 측정한다."], "외부 보고의 범위 제한", "SOURCES.md §4 · arxiv.org/html/2602.11988v1"),
      slide("절감률을 쌓을 때도 가정을 드러낸다", f"{scen['stack_saving_pct']:.3f}%", ["잔여비용에 30%, 40%, 50%, 25%, 10%를 순차 적용한 산술 결과.", "85.825%는 60–80% 범위 밖이다. ‘일치한다’는 표현은 삭제한다.", "레버의 중복·상호작용·추가 비용을 검증하지 않았다. 경험적 상한도 아니다."], "순차 잔여비용 시나리오", "experiments/exp06_other_levers.py §E"),
      slide("서브에이전트는 전체 비용으로 비교한다", "메인 + 자식 + 요약 비용", [f"동일 툴 작업 가정: naive ${scen['tool_bloat']['naive']['whole_system_usd']:.4f}, compact ${scen['tool_bloat']['compact']['whole_system_usd']:.4f}, subagent ${scen['tool_bloat']['subagent']['whole_system_usd']:.4f}", "20턴, 매 턴 툴 8,000, 초기 5,000, 출력 300, 요약 1,500, 같은 Sonnet 단가.", "기존 -87%는 자식·요약 비용이 빠진 메인 컨텍스트 계산이었다.", "동일 작업량 가정이어도 요약 품질·실패·재시도까지 같다고 검증한 것은 아니다."], "전체 시스템 비용 시나리오", "experiments/exp11_tool_output_bloat.py §A"),
      slide("라우팅은 단어보다 작업 목적을 본다", "파일 업로드 ‘구현’ → IMPLEMENT", ["설계·구현·설명 목적을 파일·검색·변환 같은 부수 단어보다 먼저 본다.", "구성한 반례 테스트는 회귀 검증이지 실사용 오류율 추정이 아니다.", "기본 tier 단가는 모델의 공식 가격이 아니라 명시적 비용 시나리오다."], "참조 구현 + 반례 회귀 테스트", "agent_setup/router.py · tests/test_regressions.py"),
      slide("사다리 재생은 정책 A/B 실측이 아니다", "리플레이는 유용하다. 명칭을 바꾼다.", ["기존 3.06배는 고정 발화를 다른 정책으로 처리한다는 비용 재생이었다.", "지금은 respec의 무료 중단과 실행 비용을 분리하고, 총 입력 증가분을 한 번만 더한다.", "A·오케스트레이터는 범위·리셋·출력 상한·진단 후 적용 비용을 공통 함수로 계산.", "새 task_id의 의도 이력을 분리해 앞 작업의 재작업 상태가 새 작업으로 새지 않게 한다."], "정책 시뮬레이션 / 소프트웨어 테스트", "analysis/lean_vs_full.py · agent_setup/orchestrator.py"),
      slide("검증기가 실패를 놓치지 않게 한다", "거짓 통과를 반례로 검사", ["슬라이드 240 → 999 변조를 거부: 실제 PPTX의 모든 텍스트와 생성 근거를 대조.", "모바일 1열 → 2열 변조, 동작 없는 메모 HTML을 브라우저 AC가 거부.", "실패 assertion은 exit 1. shell pipefail로 파이프 뒤에서도 실패를 보존.", "mock은 요청 구조·계산 검증일 뿐 새 live 측정으로 소개하지 않는다."], "오프라인 회귀·변조 테스트", "tests/ · tools/verify_deck.py · tools/browser_ac.py"),
      slide("API usage를 다룰 때의 세 가지 규칙", "캐시를 두 번 빼지 않는다", ["Gemini promptTokenCount는 캐시 입력을 포함. cost()에 전체 prompt와 cached를 전달.", "Gemini Content는 role + parts. 모델 응답의 thoughtSignature와 functionCall id를 보존.", "툴 내용은 두 번째 요청에서 처음 입력되고 세 번째 요청에서 재전송된다.", "요청 실패·절단·키 없음은 미검증/실패로 기록. 3벤더 ‘확인됨’을 미리 출력하지 않는다."], "공식 스키마 + mock 회귀", "experiments/exp10_thinking_cross_vendor.py · exp11_tool_output_bloat.py"),
      slide("숫자를 직접 확인할 수 있게 남긴다", "원자료 · 산식 · 기준일 · 재현 명령", ["results/audit_metrics.json: 저장 로그 통계 + 로컬 측정 + 시나리오를 분리한 지표.", "docs/CORRECTIONS.md: 무엇을 유지하고 무엇을 바꿨는지 상세 설명.", "SOURCES.md: 공식 단가, 논문 표, 외부 케이스의 비교 조건.", "원본 110행은 보존. 없는 원자료를 재측정 없이 만들어 넣지 않는다."], "재현 자료", "python tools/reproduce_audit.py · python tools/verify_deck.py"),
      slide("작게 바꾸고, 자기 usage와 품질로 확인한다", "영어 · 간결함 · 스펙 · 컨텍스트 관리", ["주장은 유지한다: 불필요한 생성·사고·재전송은 줄일 가치가 있다.", "배수는 모델·단가·과제·시나리오에 붙여 말한다. 절감만으로 품질을 대신하지 않는다.", "정확도·재작업·총비용을 함께 측정해 실제 배포 정책을 선택한다."], "다음 실행", "github.com/giyeop-cody/token-cost-lab"),
    ]
    assert len(A) == 29
    # Main/bonus keep their published page counts; content is generated, not copied binaries.
    main_indices = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,17,19,20,23,25,27,28]
    bonus = [slide("견적서의 나머지 항목", "조건을 명시하는 비용 절감", ["캐시 · 루프 · 스펙 · 서브에이전트 · 정책 재생", "모든 숫자에는 실측/가정의 구분이 붙는다."], "BONUS / 정정판", "docs/CORRECTIONS.md")] + [A[i] for i in (2,13,15,16,18,21,22,24,27)]
    agent_intro = slide("작은 모델이 지휘한다", "참조 구현과 효과 검증은 다르다", ["라우터 · A/B 사다리 · 의도 이력 · 출력 예산", "동작하는 배선을 검증한다. 품질 동등 절감 효과는 별도 A/B가 필요하다."], "AGENT / 정정판", "agent_setup/ · tests/")
    agent_extra = [
      slide("A와 B는 다른 실패를 처리한다", "내부 AC 실패 / 사용자 반려", ["A: 테스트가 검출한 실패를 턴 안에서 처리.", "B: 사용자 반려를 의도 이력과 함께 판정.", "검출할 AC가 부실하면 A가 놓친다. 문자열 검사만으로 기능을 보증하지 않는다."], "참조 정책", "agent_setup/router.py · ladder_b.py"),
      slide("새 작업은 별도의 상태를 가진다", "task_id별 IntentTracker", ["이전 작업의 anchor·streak·rung을 새 작업에 전달하지 않는다.", "다른 작업을 번갈아 실행해도 각자의 의도와 시도 횟수를 유지한다.", "초기화 전 inner 호출은 명시적 오류, respec은 실행 중단으로 처리."], "상태 관리 회귀", "agent_setup/orchestrator.py"),
      slide("입력 증가분은 정의부터 통일한다", "4,700을 더한다. 7,200이 아니다.", ["turn_growth_tok은 직전 출력·사용자 발화 등을 포함한 총 입력 증가분.", "출력 2,500을 다시 더하던 이중 계상을 제거.", "4,700은 페르소나 시나리오를 맞춘 값이다. 독립 실측 캘리브레이션은 아니다."], "비용 산식 교정", "analysis/calibrate_growth.py · agent_setup/config.py"),
      slide("상위 모델 진단 뒤 적용도 비용이다", "$0.05875 / 같은 단계·같은 가정", ["입력 1,800, file 범위 1.6, reset 600 → 입력 예산 3,480.", "LARGE 진단 400 출력 + MID 적용 2,500 출력을 함께 계상.", "tier 단가와 고정 입력 예산의 시나리오다. 실제 전달문 비용은 usage로 측정한다."], "공통 decision_cost 회귀", "agent_setup/router.py · orchestrator.py"),
      slide("정액제 웹 경로도 공짜는 아니다", "증분 API 비용과 총비용을 구분", ["EXTERNAL=0은 추가 종량 API 금액만 세는 모델링 선택.", "구독료·사람의 스펙 작성 시간·복사/검토 비용은 별도다.", "라우터가 웹 세션의 품질·약관 적합성을 자동 보증하지 않는다."], "비용 범위", "lab/pricing.py TIER_SCENARIOS"),
    ]
    agent = [agent_intro] + [A[i] for i in (1,11,23)] + agent_extra + [A[i] for i in (24,25,26,15,16,17,18,27,28)]
    assert len(agent) == 18
    shots = "demo/vibe_vs_spec/shots"
    case_deck = [
      slide("Vibe vs Spec", "같은 목표 페이지, 추정 usage 비교", ["카페 랜딩 · 생성 산출물 2개 · 표본 1쌍", "실제 청구 usage나 무작위 배정된 SDD 실험이 아니다."], "CASE / 정정판", "demo/vibe_vs_spec/README.md"),
      A[19],
      slide("두 산출물의 첫 화면", "같은 목표, 다른 생성 과정", ["두 장 모두 실제 생성 HTML을 Chromium 1280px에서 캡처한 화면이다.", "보이는 화면이 비슷하다는 것이 품질 동등성의 증거는 아니다."], "산출물 스크린샷", f"{shots}/vibe_top.png · {shots}/spec_top.png",
            images=[(f"{shots}/vibe_top.png", "위: Vibe 산출물 첫 화면 (1280px)"),
                    (f"{shots}/spec_top.png", "아래: Spec 산출물 첫 화면 (1280px)")]),
      slide("모바일 390px에서도 같은 1열", "정적 문자열이 아니라 실제 렌더링", ["문자열 검사만으로는 2열로 바뀌어도 통과한다.", "아래 그림은 현재 Spec 산출물을 390px에서 캡처한 것이다."], "반응형 스크린샷", f"{shots}/spec_mobile.png",
            images=[(f"{shots}/spec_mobile.png", "Spec 산출물 · 390×844 캡처")]),
      slide("전체 페이지 길이 비교", "세로로 긴 한 페이지, 두 산출물", ["원본 캡처 1,280×3,400 두 장을 같은 높이로 축소해 나란히 붙였다.", "스크롤 길이가 비슷하다는 사실은 비용·품질 동등성 판정이 아니다."], "전체 페이지 축소 비교", f"{shots}/vibe_full.png · {shots}/spec_full.png · demo/vibe_vs_spec/make_fullpage_2up.py",
            images=[(f"{shots}/vibe_spec_full_2up.png", "왼쪽 Vibe 전체 페이지 · 오른쪽 Spec 전체 페이지 (축소)")]),
      slide("입력이 늘고 비싼 출력이 줄었다", "+666 / -680 / +156", ["이 케이스에서 input과 cache는 서로 겹치지 않는 버킷으로 정의했다.", "벤더 usage 필드 이름과 동일하다고 가정하면 이중 계상할 수 있다."], "추정치 재계산", "demo/vibe_vs_spec/usage.json",
            facts=[("비캐시 입력", "486 → 1,152  (증가 666)"), ("추론+보이는 출력", "7,070 → 6,390  (감소 680)"),
                   ("캐시 입력(추정)", "312 → 468  (증가 156)"), ("합계", "7,868 → 8,010  (증가 1.8%)")]),
      slide("세 단가로 같은 추정치를 환산", "8.3% / 7.6% / 8.1% 비용 감소", ["토큰은 그대로 두고 단가와 캐시 가정만 바꾼 산술이다.", "다른 모델을 실행한 실측이 아니며, 캐시 적격성은 미확인이다."], "단가별 비용 재계산", "demo/vibe_vs_spec/cost_comparison.md · verify_case.py",
            facts=[("GPT-5 · 캐시 $0.125/M", "$0.0713465 → $0.0653985  (8.3% 감소)"),
                   ("Claude Sonnet 4.6 · 캐시 0.1×", "$0.1076016 → $0.0994464  (7.6% 감소)"),
                   ("GPT-5 · 캐시 전부 미적용", "$0.0716975 → $0.0659250  (8.1% 감소)")]),
      slide("단가비가 손익을 결정한다", "r > (666 + 156h) / 680", ["r = 출력/입력 단가, h = 캐시 읽기/입력 단가.", "모든 가격 체계에서의 보편 법칙이 아니라 고정 토큰 이동의 감도 분석이다."], "단가 민감도", "demo/vibe_vs_spec/sensitivity.py",
            facts=[("손익분기 조건", "r > (666 + 156h) / 680"), ("h = 0.1이면", "r = 1.0024"),
                   ("r → ∞ 수렴", "약 9.62% 감소에 수렴"), ("실제 청구서", "미확인 (usage 추정치 산술)")]),
      slide("품질 동등성 대신 실제 AC 범위를 공개", "정적 16항목 + 브라우저 29항목", ["390/820/821/1280px 그리드·메뉴 표시·가로 스크롤 검사", "각 카드의 내용과 세 앵커의 실제 스크롤 이동 검사", "디자인 선호도·모든 사용자 의도·두 생성 과정의 품질 동등성은 검증하지 않는다."], "현재 산출물의 실행 검사", "demo/vibe_vs_spec/verify_ac.py · tools/browser_ac.py"),
      slide("실패하는 반례도 넣는다", "모바일 2열 변조 → FAIL", ["CSS에 미디어쿼리 문자열이 있다는 것만으로 1열 전환이 보장되지 않는다.", "실제 렌더링된 gridTemplateColumns를 확인한다.", "브라우저가 없으면 PASS가 아니라 UNVERIFIED(exit 2)."], "변조 회귀", A[18]["source"]),
      A[20],
      slide("다음 실험: 스펙이 재작업을 줄이는가", "사전등록된 품질·비용 비교", ["백지 스펙 작성 비용부터 포함하고 다수 과제를 무작위 배정한다.", "같은 AC·모델·출력 예산·가격·캐시 조건으로 성공률과 총비용을 기록한다.", "진행하지 않은 실험의 절감률은 결과로 채우지 않는다."], "후속 계획 / 미실행", "demo/vibe_vs_spec/EXPERIMENT_A_PROTOCOL.md"),
    ]
    assert len(case_deck) == 12
    return {"token_cost": A, "token_cost_main": [A[i] for i in main_indices],
            "token_cost_bonus": bonus, "token_cost_agent": agent,
            "case_vibe_vs_spec/vibe_vs_spec": case_deck}


def notes_text(spec):
    """발표자 노트 — 렌더러와 검증기가 같은 함수를 쓴다(이중 구현 금지)."""
    return "\n".join([spec["scope"], *spec["lines"], *[f"{a}: {b}" for a, b in spec["facts"]],
                       *[f"그림: {c} ({a})" for a, c in spec["images"]], "근거: " + spec["source"]])


def expected_texts(spec, index):
    return [f"TOKEN COST LAB  /  {index:02d}", spec["scope"], spec["title"], spec["hero"],
            *spec["lines"], *[cell for row in spec["facts"] for cell in row],
            *[caption for _, caption in spec["images"]],
            spec["source"], "2026-09-20  ·  근거와 조건을 함께 인용"]


def fit(box_w, box_h, img_w, img_h):
    """주어진 상자에 들어가도록 비율을 유지해 (w, h, x_offset, y_offset)를 돌려준다."""
    scale = min(box_w / img_w, box_h / img_h)
    w, h = img_w * scale, img_h * scale
    return w, h, (box_w - w) / 2, (box_h - h) / 2


def render(specs, path):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.oxml.ns import qn
    prs = Presentation()
    prs.core_properties.title = specs[0]["title"]
    prs.core_properties.subject = "Evidence-consistent correction, 2026-09-20"
    prs.core_properties.author = "token-cost-lab"
    prs.core_properties.keywords = "measured logs; local encoding; explicit scenarios; see docs/CORRECTIONS.md"
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for i, spec in enumerate(specs, 1):
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        sl.background.fill.solid()
        sl.background.fill.fore_color.rgb = RGBColor.from_string("0E141B")
        stripe = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(.11), Inches(7.5))
        stripe.fill.solid(); stripe.fill.fore_color.rgb = RGBColor.from_string("36D399")
        stripe.line.fill.background()
        def text(value, name, x, y, w, h, size, color="ECF1F6", bold=False):
            sh = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
            sh.name = "audit:" + name
            tf = sh.text_frame; tf.word_wrap = True
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
            r = tf.paragraphs[0].add_run(); r.text = value
            r.font.name = "NanumGothic"; r.font.size = Pt(size); r.font.bold = bold
            r.font.color.rgb = RGBColor.from_string(color)
            for tag in ("a:latin", "a:ea", "a:cs"):
                e = r._r.get_or_add_rPr().find(qn(tag))
                if e is None:
                    e = r._r.makeelement(qn(tag), {}); r._r.get_or_add_rPr().append(e)
                e.set("typeface", "NanumGothic")
        texts = expected_texts(spec, i)
        text(texts[0], "index", .7,.3,5,.3,11,"93A4B5")
        text(texts[1], "scope", 6.3,.3,6.3,.3,11,"36D399")
        text(texts[2], "title", .7,.9,11.9,.9,29,bold=True)
        text(texts[3], "hero", .7,1.95,11.9,.85,29,"36D399",True)
        narrow = bool(spec["images"] or spec["facts"])
        for j, line in enumerate(spec["lines"]):
            text(line, f"body-{j}", .85,3.13+j*.70,7.0 if narrow else 11.65,.67,17.5)
        if spec["facts"]:
            top = 3.13 + len(spec["lines"]) * .70 + .10
            height = .46 * len(spec["facts"])
            shape = sl.shapes.add_table(len(spec["facts"]), 2, Inches(.85), Inches(top),
                                        Inches(11.65), Inches(height))
            table = shape.table
            table.first_row = False
            table.horz_banding = False
            table.columns[0].width = Inches(4.30)
            table.columns[1].width = Inches(7.35)
            for r, (label, value) in enumerate(spec["facts"]):
                for c, content in enumerate((label, value)):
                    cell = table.cell(r, c)
                    cell.margin_left = cell.margin_right = Inches(.10)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = RGBColor.from_string("111A24" if r % 2 == 0 else "18222E")
                    tf = cell.text_frame
                    tf.word_wrap = True
                    run = tf.paragraphs[0].add_run()
                    run.text = content
                    run.font.name = "NanumGothic"
                    run.font.size = Pt(14 if c else 12.5)
                    run.font.bold = bool(c)
                    run.font.color.rgb = RGBColor.from_string("ECF1F6" if c else "93A4B5")
                    for tag in ("a:latin", "a:ea", "a:cs"):
                        e = run._r.get_or_add_rPr().find(qn(tag))
                        if e is None:
                            e = run._r.makeelement(qn(tag), {}); run._r.get_or_add_rPr().append(e)
                        e.set("typeface", "NanumGothic")
        if spec["images"]:
            from PIL import Image
            box_w, top, bottom = 4.6, 2.30, 6.45
            slot = (bottom - top) / len(spec["images"])
            for k, (relative, caption) in enumerate(spec["images"]):
                with Image.open(ROOT / relative) as im:
                    w, h, dx, dy = fit(box_w, slot - .32, *im.size)
                sl.shapes.add_picture(str(ROOT / relative), Inches(8.05 + dx),
                                      Inches(top + k * slot + dy), Inches(w), Inches(h))
                text(caption, f"image-caption-{k}", 8.05, top + k * slot + slot - .30, box_w, .28,
                     9.5, "93A4B5")
        text(spec["source"], "source", .7,6.65,12,.30,10,"93A4B5")
        text(texts[-1], "footer", .7,7.02,12,.28,10,"93A4B5")
        sl.notes_slide.notes_text_frame.text = notes_text(spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(path)


def script_text(specs):
    content = f"# {specs[0]['title']} — 정정판 대본\n\n{len(specs)}장 · 2026-09-20 · 생성 원천: `presentation/deckgen/build_verified.py`와 원자료.\n\n"
    for i, spec in enumerate(specs, 1):
        content += f"## {i}. {spec['title']}\n\n**{spec['hero']}** · {spec['scope']}\n\n"
        content += "\n".join("- " + t for t in spec["lines"]) + "\n\n"
        if spec["facts"]:
            content += "\n".join(f"| {a} | {b} |" for a, b in spec["facts"]) + "\n\n"
        if spec["images"]:
            content += "\n".join(f"![{c}](../{a})" for a, c in spec["images"]) + "\n\n"
        content += f"근거: `{spec['source']}`\n\n"
    return content.rstrip() + "\n"


def build_all(output=None, evidence=None):
    output = Path(output or ROOT / "presentation")
    evidence = evidence or build()
    decks = specifications(evidence)
    for key, specs in decks.items():
        render(specs, output / (key + ".pptx"))
        script_name = {"token_cost": "script", "token_cost_main": "script_main", "token_cost_bonus": "script_bonus",
                       "token_cost_agent": "script_agent", "case_vibe_vs_spec/vibe_vs_spec": "case_vibe_vs_spec/script_case"}[key]
        content = script_text(specs)
        (output / (script_name + ".md")).write_text(content, encoding="utf-8")
        print(f"generated {key}.pptx ({len(specs)} slides)")
    return decks


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path)
    args = ap.parse_args()
    build_all(args.out_dir)


if __name__ == "__main__":
    main()
