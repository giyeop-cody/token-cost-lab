#!/usr/bin/env python3
"""발표용 슬라이드 + 발표자 노트(대본)의 단일 생성 원천.

원칙: 슬라이드에는 **메시지와 숫자**만 둔다. 검증 범위·한계·반례·질문 대비는
발표자 노트(notes_text)로 내린다. 숫자는 lab.evidence.build()와 실행 로그에서만 가져오고,
검증기(tools/verify_deck.py)가 이 명세를 실제 PPTX·PDF 텍스트와 그대로 대조한다.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lab.evidence import build


def slide(title, hero, lines, scope, source, script, images=None, facts=None):
    """script: 발표 멘트(문단 리스트). 검증 범위·한계·질문 대비를 여기에 적는다."""
    return dict(title=title, hero=hero, lines=lines, scope=scope, source=source, script=script,
                images=images or [], facts=facts or [])


CHARTS = ROOT / "presentation/charts"


def chart_manifest():
    """차트 생성기가 남긴 계열값·해시. 차트 파일과 슬라이드의 단일 대조 기준이다."""
    path = CHARTS / "manifest.json"
    if not path.is_file():
        raise SystemExit("UNVERIFIED: presentation/charts/manifest.json 없음 — "
                         "python presentation/deckgen/make_charts.py 를 먼저 실행하세요.")
    return json.loads(path.read_text(encoding="utf-8"))["charts"]


def chart(filename, title, hero, lines, scope, source, script, facts=None):
    """차트 슬라이드: 메시지는 위(제목·강조·한 줄), 그래프는 아래 전폭."""
    entry = next((v for v in chart_manifest().values() if v["file"] == filename), None)
    if entry is None:
        raise SystemExit(f"UNVERIFIED: {filename} 이 charts/manifest.json에 없습니다")
    spec = slide(title, hero, lines, scope, source, script, facts=facts)
    caption = f"그래프 · {entry['caption_ko']} · {filename}"
    spec["chart"] = {"file": str(CHARTS.relative_to(ROOT) / filename), "caption": caption}
    return spec


def specifications(e):
    import json
    gaps = {name: json.loads((ROOT / path).read_text(encoding="utf-8"))["year_gap"]
            for name, path in (("current", "demo/results_current.json"), ("legacy", "demo/results.json"))}
    f = e["flores"]
    tok = f["tokenizers"]
    sw = e["thinking_sweep"]
    ratios = sw["ratios"]
    lang = e["language"]
    scen = e["scenarios"]
    case = e["estimated_case_price_sensitivity"]["models"]["gpt5"]
    sonnet = e["estimated_case_price_sensitivity"]["models"]["sonnet"]
    corpus = "tools/parallel_tokenizer_bench.py · FLORES-200 devtest"
    logs = "tools/stats_test.py · storage logs"
    sweep_src = "results/thinking_sweep.jsonl (30 rows)"
    shots = "demo/vibe_vs_spec/shots"

    # ── 차트 슬라이드 (presentation/charts/*.png, make_charts.py가 생성) ──
    prices_chart = chart(
        "prices.png", "같은 토큰, 다른 단가", "출력은 입력의 4~8배",
        ["비싼 쪽(출력)을 줄이는 습관이 먼저다",
         "캐시 읽기는 입력의 0.1배 — 캐시가 있는 이유"],
        "가격표 스냅샷 (2026-09-20)", "lab/pricing.py MODELS",
        ["공개 리스트 단가이며 계약·무료 티어·세금·도구 비용은 별도다.",
         "출력÷입력 배수는 모델별로 4~8배다. 같은 배수를 모든 모델에 적용하지 않는다.",
         "Gemini 3.8/3.6 Flash의 인트로 단가는 2026-12-31까지이며 이후 2배가 된다 — 표에 넣은 값의 기준일을 밝힌다."])
    tokenizer_chart = chart(
        "tokenizer.png", "한국어는 같은 내용에 토큰을 더 쓴다", "1.4723배 · 2.3669배",
        ["FLORES-200 대응 번역 1,012쌍을 전수 인코딩",
         "글자 수로 자르면 한국어가 먼저 잘린다"],
        "로컬 토크나이저 실측", corpus,
        ["배수는 토큰 합계의 비율이다. 대응 번역문이므로 '같은 내용' 전제가 성립한다.",
         "이 배수를 그대로 비용으로 환산하지 않는다. 비용은 생성 길이와 사고량이 함께 결정한다.",
         "토큰/글자는 인코딩 비율이지 내용·의미의 비율이 아니다."])
    cache_chart = chart(
        "cache.png", "캐시는 조건이 맞을 때만 이득", "$8.55 → $3.219 (-62%)",
        ["프리픽스를 매번 바꾸면 $10.05 (+17.5%)",
         "고정 블록을 앞으로 모아 적중률을 올린다"],
        "비용 시나리오 (100콜)", "experiments/exp03_prompt_caching.py",
        ["고정 20,000 + 가변 1,000 + 출력 1,500, Sonnet 단가, 100콜 조건의 계산이다.",
         "히트율은 가정값이다. 실제 값은 자기 usage의 cache_read 필드로 측정한다.",
         "저장료·TTL·최소 길이는 모델별로 다르다. 미확인 기준은 할인 가정을 하지 않는다."])
    turns_chart = chart(
        "turns.png", "긴 세션일수록 가파르다", "5턴 $0.26 → 50턴 $12.09",
        ["20턴에 컴팩션을 걸면 $0.93 (60% 절감)",
         "안 쓰는 코드도 매 턴 다시 실려 과금된다"],
        "비용 시나리오", "experiments/exp04_agent_loop_sdd.py",
        ["고정 8,000토큰 프리픽스, 턴당 입력 2,000·출력 800, Sonnet 단가의 계산이다.",
         "컴팩션 주기는 요약 비용과 품질·재작업을 함께 측정해 정한다.",
         "실제 세션 비용은 도구 출력과 파일 재전송으로 더 커진다."])
    stack_chart = chart(
        "stack.png", "다섯 레버를 겹치면", "잔여 14.18%",
        ["시맨틱 캐시 → 라우팅 → 캐싱 → effort → 배치",
         "각 레버가 자기 조건을 만족할 때의 순차 산술"],
        "순차 시나리오", "experiments/exp06_other_levers.py",
        ["각 레버의 절감률을 순서대로 곱한 값이다. 실제 도입에서는 서로 겹치는 부분이 생긴다.",
         "검증된 상한도 아니다. 자기 데이터로 A/B를 돌려 확정해야 한다.",
         "레버별 적용 조건(히트율·라우팅 임계값·배치 가능성)이 다르다."])
    thinking_chart = chart(
        "thinking.png", "사고 예산을 적지 않으면 기본값이 정한다", "미지정 대비 199.47배",
        ["미지정 $0.000028 vs 자동 $0.00558525 (호출당)",
         "예산을 명시하는 순간 청구서가 예측 가능해진다"],
        "저장 API 로그 재계산", sweep_src,
        ["비교는 자동(-1) 대 미지정이다. 명시적 0과 섞으면 결론이 달라진다.",
         "±$0.05 허용오차 통과는 미지정 6/6 · 명시적 0은 5/6이며 동등성 증명이 아니다.",
         "구모델의 thinkingBudget 로그는 역사적 관측으로 보존한다."])
    case_tokens_chart = chart(
        "case_tokens.png", "무엇이 비용을 움직였나", "합계 7,868 → 8,010 (+1.8%)",
        ["비캐시 입력 ↑ · 추론+출력 ↓",
         "합계는 거의 그대로, 구조만 바뀌었다"],
        "추정치 재계산", "demo/vibe_vs_spec/usage.json",
        ["세션 추정치이며 실제 청구 usage가 아니다. 표본 1쌍이다.",
         "추론 토큰은 출력 요율로 과금된다는 가정을 쓴다.",
         "표의 버킷 정의(비캐시 입력·출력·캐시)는 벤더 usage 필드와 이름이 같다고 가정하면 이중 계상할 수 있다."])
    case_bases_chart = chart(
        "case_bases.png", "단가가 바뀌어도 방향은 같다", "감소 8.3% · 7.6% · 8.1%",
        ["같은 추정 usage를 세 단가로 환산",
         "출력 단가가 높을수록 격차가 커진다"],
        "단가별 비용 재계산", "presentation/case_vibe_vs_spec/cost_comparison.md",
        ["다른 모델을 실행한 실측이 아니라 같은 추정 토큰의 산술이다.",
         "캐시 적격성은 확인하지 않았고, 캐시 미적용 환산이 가장 보수적인 8.1%다.",
         "실제 청구서 대조는 하지 않았다."])

    A = [
      slide("시키지도 않은 시공비 청구서", "같은 결과물, 다른 청구서",
            ["모델은 세 가지로 청구한다 — 입력 · 출력 · 사고",
             "오늘은 그 청구서를 줄이는 습관 다섯 가지를 다룬다",
             "숫자는 실측 · 로그 재계산 · 가정 시나리오를 구분해 말한다"],
            "발표 · 2026-09-20", "github.com/giyeop-cody/token-cost-lab",
            ["인사와 함께 오늘 목표를 한 줄로 말한다: \"같은 결과물을 더 싸게 사는 방법\".",
             "세 가지 청구 항목(입력·출력·사고)을 미리 짚어 두면 뒤의 숫자가 이해된다.",
             "숫자의 성격(실측/재계산/가정)을 먼저 밝힌다 — 질문이 몰리지 않는다."]),
      slide("오늘 가져갈 결론", "비용은 모델이 아니라 습관이 만든다",
            ["영어로 생각하고, 필요한 언어로 답한다",
             "설명은 최소로, 추론 강도는 작업에 맞춰",
             "결정을 스펙으로 먼저 주고, 반복되는 접두부는 캐싱한다"],
            "결론 요약", "README.md",
            ["다섯 원칙을 한 장으로 선요약한다. 청중이 결론을 미리 알고 들으면 뒤가 훨씬 빨리 이해된다.",
             "원칙은 유지한다는 점을 명확히 한다. 오늘 바뀌는 것은 원칙이 아니라 숫자의 조건과 증거다.",
             "질문이 나오면 \"뒤에서 근거와 한계를 함께 말한다\"고 안내하고 넘어간다."]),
      slide("청구서의 구조", "출력은 입력의 2~8배",
            ["캐시된 입력과 비교하면 최대 50배까지 벌어진다",
             "사고 토큰은 출력 단가로 청구된다",
             "그래서 '덜 쓰기'보다 '다시 안 보내기'가 크다"],
            "가격표 실측", "experiments/exp02_output_to_input.py",
            ["입력은 한 번에 병렬 처리되고 출력은 한 토큰씩 생성되기 때문에 단가가 다르다.",
             "캐시 읽기 단가는 입력의 0.1배 수준(모델별로 다름)이다. 이 비대칭이 오늘 전략의 근거다.",
             "가격은 공개 리스트 기준이며 계약·무료 티어·세금·도구 비용은 별도다. 실제 청구서로 검증해야 한다."]),
      prices_chart,
      slide("원칙 1 · 영어로 생각하고, 필요한 언어로 답한다",
            f"같은 내용에 {tok['o200k_base']['ko_en_ratio']:.4f}배 · 구형 {tok['cl100k_base']['ko_en_ratio']:.4f}배",
            [f"FLORES-200 대응 번역 {f['n_pairs']:,}쌍을 전수 인코딩해 토큰 합계를 비교",
             "짧고 압축된 문장일수록 격차가 커진다",
             "사용자에게는 한국어로 답한다 — 안 보이는 사고만 영어로"],
            "로컬 토크나이저 실측", corpus,
            ["숫자는 토큰 합계의 비율이다. 대응 번역문이므로 '같은 내용'이라는 전제가 성립한다.",
             "이 배수를 그대로 비용으로 환산하지 않는다. 실제 비용은 생성 길이와 사고량이 함께 결정한다.",
             "반례도 있다: 모델·과제·언어별로 효과가 다르다. 자기 워크로드로 다시 측정하는 것이 결론이다.",
             "답변 언어를 바꾸라고 말하는 것이 아니라, 내부 추론 단계에서 영어 활용을 권하는 것이다."]),
      slide("왜 한국어가 더 쪼개지는가", "토큰/글자 0.204 vs 0.526",
            ["어휘 20만 개 중 한글은 약 1.2%",
             "'에이전트'는 4토큰, ' agent'는 1토큰",
             "512토큰이 영어 2,513자 · 한국어 973자 — 글자 수로 자르면 한국어 문서가 잘린다"],
            "인코딩 실측", "experiments/exp01_tokenizer_ko_en.py",
            ["RAG 청킹을 글자 수 기준으로 잡으면 한국어 청크만 조용히 잘리거나 한도를 넘는다.",
             "토큰/글자 비율은 인코딩 비율이지 내용·의미의 비율이 아니다. 글자 수를 의미량으로 읽으면 틀린다.",
             "실무 규칙: 청크 상한은 토크나이저로 세고, 글자 수 기준값에 안전계수를 두지 말고 토큰으로 통일한다."]),
      tokenizer_chart,
      slide("원칙 2 · 설명을 최소화한다", "342 → 58 토큰 (83% 감소)",
            ["월 1,760건 기준 $9.03 → $1.53",
             "'코드를 읽으면 아는 문장'만 지운다 — 코드는 그대로",
             "샘플은 차이를 보이려고 극단적으로 잡았다. 자기 작업으로 다시 재라"],
            "인코딩 실측", "experiments/exp05_verbosity_effort.py",
            ["같은 결과물을 세 가지 설명 스타일로 생성해 인코딩 토큰을 측정한 값이다(보통 90토큰, 장황 342토큰).",
             "품질·정확도 동등성을 별도로 검정한 것은 아니다. 어려운 작업에서는 설명이 검증에 필요할 수 있다.",
             "발표에서는 '실무 기준선은 자기 작업에서 재측정'을 반드시 덧붙인다."]),
      slide("원칙 3 · 추론 강도를 작업에 맞춘다", "월 $924 → $118 (70% 절감)",
            ["minimal $7.92 · medium $132 · max $924",
             "설계 10%만 high, 정형·단순 작업은 low",
             "reasoning/output 비율이 0.8을 넘으면 과다 신호"],
            "시나리오 (사고 토큰 가정)", "experiments/exp05_verbosity_effort.py",
            ["사고 토큰은 눈에 안 보이지만 출력 단가로 청구된다. 단계별 비용은 사고량 가정의 시나리오다.",
             "effort를 낮추면 어려운 작업의 정확도가 떨어질 수 있다. '전부 낮춰라'가 아니라 '작업에 맞춰라'다.",
             "정확도 게이트를 함께 두고 배분표를 만들 것을 권한다."]),
      slide("원칙 4 · 결정을 스펙으로 먼저 준다",
            f"재작업 5 → 2 사이클, {scen['sdd']['cold']['saving_pct']:.1f}% 절감",
            ["스펙 4,000토큰 작성 비용도 포함한 계산",
             "얕은 스펙만으로도 36.9% 절감",
             "설명이 아니라 결정을 적는다 — 페이지 · 스택 · 디자인 · 수용 기준"],
            "비용 시나리오 (턴 가정)", "experiments/exp04_agent_loop_sdd.py",
            ["40턴→12턴 감소는 모델의 입력 가정이지 관측이 아니다. 실제 턴 감소는 미측정이다.",
             "예열 캐시를 가정하면 71.0%가 나오지만, 기본값은 사이클마다 첫 쓰기 비용을 포함한 68.7%다.",
             "외부 반례: 저장소 컨텍스트 파일을 자동 생성하면 비용이 늘고 성공률이 떨어진 조건도 보고됐다. 결론은 '짧고 결정만'."]),
      slide("원칙 5 · 턴 수가 비용을 지배한다", "턴 2배 → 비용 3.1배",
            ["5턴 $0.26 · 20턴 $2.32 · 50턴 $12.09",
             "안 쓰는 코드도 매 턴 다시 실려 과금된다 (YAGNI)",
             "컨텍스트는 길이보다 '반복'이 비쌉니다"],
            "비용 시나리오", "experiments/exp04_agent_loop_sdd.py",
            ["에이전트 비용은 턴 수의 2차 함수다. '한 번 더 물어보기'가 싼 행동이 아니다.",
             "추상화 레이어 3개를 미리 만든 경우 20턴 세션에서 추가 재전송 비용 $0.270이 붙는다(가정).",
             "턴을 줄이는 가장 확실한 수단은 요구사항을 먼저 확정하는 것이다."]),
      turns_chart,
      slide("캐싱 · 오늘 바로 켤 수 있는 레버",
            f"${scen['cache']['no_cache_usd']:.2f} → ${scen['cache']['cache_usd']:.2f} ({scen['cache']['saving_pct']:.1f}% 절감)",
            ["쓰기 프리미엄은 두 번째 호출에서 회수된다",
             "고정 블록(시스템 · 툴 정의 · 규약)을 맨 앞으로 모은다",
             "최소 길이를 확인한다 — Haiku 4.5는 4,096토큰"],
            "비용 시나리오 (100콜)", "experiments/exp03_prompt_caching.py",
            ["고정 20,000 + 가변 1,000 + 출력 1,500, Sonnet 단가, 100콜 조건의 계산이다.",
             "히트율은 가정값이다. 실제 값은 자기 usage의 cache_read 필드로 측정해야 한다.",
             "저장료·TTL·최소 길이는 모델별로 다르다. 미확인 기준은 할인 가정을 하지 않는다."]),
      slide("캐시를 깨는 한 줄", f"${scen['cache']['all_miss_usd']:.2f} (17.5% 더 지출)",
            ["맨 앞의 타임스탬프·요청 ID는 매번 미스로 만든다",
             "변하는 값은 반드시 뒤로 보낸다",
             "미스 상태의 캐싱은 안 쓰느니만 못하다"],
            "비용 시나리오", "experiments/exp03_prompt_caching.py",
            ["캐시는 프리픽스를 단위로 매칭한다. 앞부분이 한 글자만 달라도 전액을 다시 낸다.",
             "히트율 0%에서는 쓰기 프리미엄만 계속 물어 캐시 없음($8.55)보다 비싸진다($10.05).",
             "반대로 히트율이 40%만 넘어도 이미 이득이다. 그래서 '켜고, 적중률을 본다'가 순서다."]),
      cache_chart,
      slide("압축과 캐싱은 대체재가 아니다",
            f"${scen['compression_cache']['cached']:.4f} → ${scen['compression_cache']['both']:.4f} (94% 절감)",
            [f"그냥 캐싱 ${scen['compression_cache']['cached']:.4f} vs 절반 요약 ${scen['compression_cache']['compressed']:.4f}",
             "지울 수 있는 반복은 지우고, 지울 수 없는 반복은 고정해 캐시에 태운다",
             "압축률이 높을수록 조합의 이득도 커진다"],
            "비용 시나리오", "experiments/exp09_dry.py",
            ["같은 12,000토큰을 매번 보내던 세션을 절반으로 줄이고 캐시까지 걸었을 때의 산술이다.",
             "압축률과 정확도는 작업별로 다르다. 지시·수용 기준을 지우면 요구사항이 바뀐다.",
             "압축기 실행 비용과 지연도 손익에 포함해야 한다. 짧은 프롬프트는 압축이 손해일 수 있다.",
             "압축 자체의 지연·품질 손실은 이 계산 밖이다."]),
      slide("긴 세션은 컴팩션으로 접는다", "$2.32 → $0.93 (60% 절감)",
            ["10턴마다 접으면 $1.23 (47% 절감)",
             "너무 자주 접으면 요약 호출이 이득을 먹는다",
             "최적 주기는 세션 길이와 요약 비용으로 정해진다"],
            "비용 시나리오", "experiments/exp04_agent_loop_sdd.py",
            ["20턴 세션에 캐싱만 걸면 $1.91(+17%) — 이력 누적은 그대로 남기 때문이다.",
             "요약은 품질에 영향을 준다. 압축 과정에서 잃는 정보가 재작업을 만들면 절감이 상쇄된다.",
             "주기를 바꿔 가며 재작업률과 총비용을 함께 측정할 것을 권한다."]),
      slide("툴 출력과 서브에이전트는 전체 비용으로 본다",
            f"${scen['tool_bloat']['naive']['whole_system_usd']:.4f} → ${scen['tool_bloat']['subagent']['whole_system_usd']:.4f}",
            ["툴 읽기 누적 전송 1,680,000 토큰 (20턴)",
             "컴팩션 $3.4425 · 서브에이전트 $2.736",
             "자식 호출·요약 비용까지 포함해 비교한다"],
            "전체 시스템 비용 시나리오", "experiments/exp11_tool_output_bloat.py",
            ["같은 툴 작업량을 가정하고 메인·자식·요약 비용을 모두 합산한 값이다.",
             "서브에이전트는 요약 품질과 실패·재시도 특성이 다르다. 비용만으로 우열을 단정하지 않는다.",
             "과거의 -87%는 자식·요약을 빼고 계산한 값이어서 전체 절감으로 쓰지 않는다."]),
      slide("모델 라우팅 · 쉬운 요청에 비싼 모델을 쓰지 않는다",
            "전부 강 $350 → 절반 $184",
            ["절반만 라우팅해도 47% 절감",
             "공격적 라우팅은 $35.17 (90% 절감)",
             "품질 측정 도구가 먼저다 — 임계값은 주기적으로 재보정"],
            "시나리오 (10,000콜)", "experiments/exp06_other_levers.py",
            ["벤치마크에서 잡은 임계값을 그대로 프로덕션에 쓰면 절감이 과대 추정된다.",
             "저볼륨에서는 라우팅 오버헤드가 절감을 상쇄한다. 반복률과 볼륨을 먼저 본다.",
             "라우터 오류율·검출률은 이 저장소에서 측정하지 않았다. 참조 구현의 회귀 테스트만 있다."]),
      slide("배치 API · 지연을 할인으로 바꾼다", "50,000건 $675 → $337.50",
            ["입력·출력 모두 50% 할인",
             "24시간 안에 끝나면 되는 잡만",
             "야간 평가 · 대량 분류 · 리포트 생성 · 레포 전체 분석"],
            "가격표 + 시나리오", "experiments/exp06_other_levers.py",
            ["토큰 수는 그대로이고 지원 서비스에서 가격을 줄이는 레버다.",
             "실시간 UI, 대화형 코딩 에이전트처럼 대기 화면이 있는 작업에는 쓸 수 없다.",
             "지연·실패 처리·지원 조건(요청 수 상한, 결과 보관 기간)을 확인해야 한다."]),
      slide("두 습관, 같은 결과물",
            f"페르소나 {scen['personas']['current']['ratio']:.1f}배 (기존 가정 {scen['personas']['legacy']['ratio']:.1f}배)",
            ["A: 6턴 · 전체 재출력 · 과한 사고 / B: 2턴 · 짧은 패치",
             f"연 환산 ${gaps['current']} 차이 (기존 가정 ${gaps['legacy']})",
             "같은 작업 1,760건/년을 가정한 비교"],
            "시나리오", "demo/compare_personas.py",
            ["두 조건 모두 추정 usage와 가정으로 만든 비용 모형이다. 실제 정책 A/B가 아니다.",
             "품질 동등성이나 완료 작업당 절감률은 검증하지 않았다.",
             "기존 20.8배는 역사적 가정(사고 언어 승수 1.44, 캐시 최소 길이 무시)으로 보존한다."]),
      slide("레버는 곱해진다", f"{scen['stack_saving_pct']:.3f}% (잔여 14%)",
            ["시맨틱 캐시 → 라우팅 → 캐싱 → verbosity/effort → 배치",
             "잔여 비용에 순차 적용한 산술 결과",
             "레버 간 중복·상호작용은 검증하지 않았다"],
            "순차 시나리오", "experiments/exp06_other_levers.py",
            ["각 레버의 절감률을 순서대로 곱한 값이다. 실제 도입에서는 서로 겹치는 부분이 생긴다.",
             "검증된 상한도 아니다. 자기 데이터로 A/B를 돌려 확정해야 한다.",
             "발표에서는 '이론적 상한'이라는 표현보다 '순차 가정의 산술'이라고 말한다."]),
      slide("작은 모델이 지휘한다", "사다리 2.81배 (1턴 27% · 2턴 43%)",
            ["실패가 반복되면 격차가 커진다 — 6회 2.80배",
             "짧은 리워크에서도 이득 — 1턴 27% · 2턴 43%",
             "respec이면 실행 전에 멈추므로 실행 비용만 계산"],
            "정책 시나리오 재생", "analysis/lean_vs_full.py",
            ["고정 발화를 두 정책으로 처리했을 때의 지출 차이다. 실제 A/B 실측이 아니다.",
             "'12배' 같은 큰 수치는 대조군을 최상위 모델로 잡았을 때만 나온다 — 그 조건을 말하지 않으면 과장이 된다.",
             "1턴·2턴처럼 짧은 리워크에서도 이득이 나는지가 도입 판단의 핵심이다.",
             "이 값은 정책 지출 모형의 재생값이다. respec 경로는 실행을 하지 않으므로 지출이 늘지 않는다."]),
      stack_chart,
      slide("안 보이는 사고 토큰",
            f"{ratios['actual']['auto_unspecified']:.2f}배 (기존 환산 {ratios['legacy']['auto_unspecified']:.2f}배)",
            ["같은 문제를 조건당 6회 실행한 저장 로그 30행",
             "사고가 난 호출에서 사고 토큰 비중 99.625%",
             "예산을 지정하지 않으면 사실상 '무제한' — 명시적으로 정한다"],
            "저장 API 로그 재계산", sweep_src,
            ["비교는 자동(-1) 대 미지정이다. 명시적 0과 섞으면 결론이 달라진다.",
             "±$0.05 허용오차 통과는 미지정 6/6 · 명시적 0은 5/6이다. 정확한 숫자 채점으로는 3/6이 된다 — 동등성 증명이 아니다.",
             "구모델의 thinkingBudget 로그는 역사적 관측으로 보존한다. 현재 API는 thinkingLevel을 쓴다."]),
      slide("언어별 비용은 지표마다 다르다", "호출당 1.364배 · 0.729배",
            ["문자당(기존 환산 단가) 3.027배 · 1.363배",
             "같은 과제라도 언어에 따라 생성 길이가 달라진다",
             "지표를 섞으면 결론이 뒤집힌다"],
            "저장 로그 80행 재계산", logs,
            ["호출당 비용과 문자당 비용은 다른 질문에 대한 답이다. 하나로 다른 것을 대신하지 않는다.",
             "'한국어가 일을 덜 했다'거나 '싸 보이는 착시'로 해석하지 않는다.",
             "검정은 Welch로 계산했고 네 비교 모두 유의하다. 다만 반복 호출의 조건부 검정이며 의미량·정확도 검정이 아니다."]),
      slide("사례 · 카페 랜딩 한 페이지", "토큰 +1.8% · 비용 8.3% 감소",
            ["한 문장 지시 vs 4필드 스펙 — 같은 목표",
             "GPT-5 8.3% · Sonnet 7.6% · 캐시 미적용 8.1%",
             "입력은 늘고, 비싼 출력은 줄었다"],
            "추정 usage 재계산", "demo/vibe_vs_spec/README.md",
            ["실제 청구 usage가 아니라 세션 추정치다. 절대값과 상대 차이 모두 추정 오차가 있다.",
             "캐시 적격성은 확인하지 않았다. 전부 신규 입력으로 환산한 값도 함께 공개한다.",
             "Spec 산출물은 Vibe 결과를 역산한 것이다. 백지 스펙 작성 비용과 재작업 감소는 통제하지 않았다.",
             "표본 1쌍의 사례이며 일반화하지 않는다."]),
      case_tokens_chart,
      slide("사례 · 무엇을 확인했나", "정적 16 + 브라우저 29항목",
            ["390 · 820 · 821 · 1280px 실제 렌더링 검사",
             "카드 내용 · 앵커 이동 · 가로 스크롤 · JS 오류 0건",
             "통과 여부는 실행 로그에 남는다"],
            "실동작 검사 (Chromium)", "demo/vibe_vs_spec/verify_ac.py",
            ["문자열 검사는 동작을 보증하지 않는다. 그래서 실제 브라우저 렌더링을 검사한다.",
             "변조 반례(모바일을 2열로 바꾼 HTML)를 넣어 검사가 실제로 실패하는지도 확인했다.",
             "브라우저가 없으면 PASS가 아니라 UNVERIFIED로 종료한다. 검사 항목 수는 실행 로그에 있다.",
             "디자인 선호와 품질 동등성은 검증 대상이 아니다."]),
      case_bases_chart,
      slide("적용 우선순위", "1~3번은 오늘 오후에 켤 수 있다",
            ["낮은 난이도: 캐싱 · verbosity/effort · 배치",
             "중간: 스펙 먼저 · 컴팩션",
             "높은 난이도: 라우팅 · 시맨틱 캐시 · 압축"],
            "적용 순서", "experiments/exp06_other_levers.py",
            ["난이도는 되돌리기 쉬운 순서이기도 하다. 앞의 3개는 설정 변경으로 시작할 수 있다.",
             "라우팅과 시맨틱 캐시는 품질 측정 도구가 있어야 안전하다.",
             "우선순위 표에 적힌 조건(모델별 최소 프리픽스 길이 등)을 실제로 확인하고 켠다."]),
      slide("팀에 붙이는 순서", "측정 → 적용 → 재측정",
            ["usage 로그로 자기 배수를 먼저 잰다",
             "고정 접두부를 앞으로, 변하는 값은 뒤로",
             "캐시 적중률과 reasoning/output 비율을 대시보드로 본다"],
            "적용 절차", "README.md",
            ["측정 없이 절감률을 목표로 잡으면 품질을 깎아서 숫자를 맞추게 된다.",
             "적용 후 재측정을 하지 않으면 프롬프트가 바뀌면서 효과가 조용히 사라진다.",
             "캐시 적중률이 50% 아래면 프롬프트 앞부분의 변동 요소를 먼저 의심한다."]),
      slide("흔한 실수 다섯", "미스 캐싱 · 과잉 추론 · 전체 재출력 · 오배치 라우팅 · 무제한 사고",
            ["캐시를 켜놓고 프리픽스를 매일 바꾼다",
             "'전체 파일 다시 써줘'로 출력을 다시 산다",
             "라우팅 임계값을 벤치마크 값 그대로 쓴다"],
            "실무 체크", "docs/CORRECTIONS.md",
            ["다섯 가지 모두 '켜면 좋다'는 조치를 조건 없이 적용해서 생긴다.",
             "특히 캐싱은 켠 상태에서 미스가 나면 비용이 더 늘어난다 — 적중률을 보지 않으면 손해다.",
             "사고 예산은 지정하지 않으면 기본값이 정한다. 기본값을 모르면 청구서를 예측할 수 없다."]),
      slide("캐싱과 개인정보", "개인화 · 실시간 응답은 캐싱 금지",
            ["멀티턴은 캐시 키에 컨텍스트를 포함",
             "시맨틱 캐시 임계값이 느슨하면 '비슷하지만 틀린 답'을 준다",
             "삭제·TTL 정책을 프롬프트 설계와 함께 정한다"],
            "운영 주의", "experiments/exp06_other_levers.py",
            ["캐시는 비용 레버이면서 데이터 보존 문제다. 개인정보가 섞인 접두부는 캐싱 대상에서 뺀다.",
             "시맨틱 캐시는 질의가 비슷할 때 호출 자체를 제거한다. 히트율보다 오답 위험이 먼저다.",
             "TTL과 삭제 시점을 벤더 문서 기준으로 확인하고 기록해 둔다."]),
      slide("직접 확인하는 방법", "python run_all.py (유료 호출 0)",
            ["실험 11종이 오프라인으로 전부 재현된다",
             "원자료 · 로그 · 검증 스크립트 · 발표 덱 생성기를 함께 공개",
             "덱과 대본도 같은 원천에서 생성된다"],
            "재현", "tools/reproduce_audit.py",
            ["터미널에서 오늘 본 표를 그대로 다시 볼 수 있다. 유료 API 호출은 0회다.",
             "덱의 모든 텍스트는 생성 원천과 대조해 검증한다. 숫자를 손으로 고치면 검증이 실패한다.",
             "검증 항목 수는 본문에 고정하지 않고 실행 결과 파일로 남긴다."]),
      slide("작게 시작해서 자기 usage로 확인한다", "오늘 한 가지만 켜라 — 캐시",
            ["다음 주에 배수와 적중률을 다시 잰다",
             "품질 게이트를 함께 둔다 — 절감만으로 대신하지 않는다",
             "질문과 재현 결과는 저장소 이슈로 남긴다"],
            "마무리", "github.com/giyeop-cody/token-cost-lab",
            ["오늘 배운 것을 다 적용하지 말고 되돌리기 쉬운 것 하나만 켜고 재측정한다.",
             "절감률은 자기 데이터에서 나온 값이어야 한다. 이 자료의 숫자는 출발점이다.",
             "발표 자료의 근거·한계·정정 이력은 저장소 문서에 그대로 남아 있다."]),
    ]
    assert len(A) == 36

    # 본편: 원칙 5개 + 핵심 차트 + 카페 사례 + 적용 절차 (심화 레버 일부는 보너스로)
    main_indices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 19, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]
    token_cost_main = [A[i] for i in main_indices]
    assert len(token_cost_main) == 27

    bonus = [A[11], A[12], A[13], A[14], A[15], A[16], A[17], A[18], A[19], A[23], A[24], A[25], A[33], A[35]]
    bonus[0] = slide("견적서의 나머지 항목", "원칙 5개로 다 못 줄인 비용은 어디 있나",
                     ["캐싱 · 압축 · 컴팩션 · 서브에이전트 · 라우팅 · 배치",
                      "각 레버의 조건과 함정을 한 장씩 본다",
                      "레버는 곱해진다 — 우선순위는 뒤에서"],
                     "심화 세션", "docs/CORRECTIONS.md",
                     ["본편에서 다 못 다룬 레버를 심화한다. 각 레버는 '켜는 조건'과 '깨지는 조건'이 한 쌍이다.",
                      "심화 세션이므로 숫자의 가정(모델 단가·토큰 수)을 슬라이드마다 확인한다.",
                      "마지막에 우선순위와 보안 주의로 정리한다."])
    assert len(bonus) == 14

    agent_intro = slide("작은 모델이 지휘한다", "라우팅 · 사다리 · 상태 분리 · 예산",
                        ["모든 요청에 최상위 모델을 쓰지 않는다",
                         "실패가 반복되면 그때 올린다",
                         "작업별 상태와 비용을 코드로 관리한다"],
                        "AGENT / 2026-09-20", "agent_setup/ · tests/",
                        ["에이전트 셋팅편이다. 목표는 '기본값을 낮추고, 필요할 때만 올리는' 배선이다.",
                         "오늘 보여주는 것은 참조 구현과 회귀 테스트다. 절감 효과의 실제 A/B는 별도 실험이 필요하다.",
                         "라우터 오류율·검출률은 측정하지 않았고, 그렇게 표기한다."])
    agent_extra = [
      slide("무엇을 자동화하는가", "요청마다 사람이 모델을 고르지 않는다",
            ["설계 · 구현 · 설명 · 정형 작업을 분류해 티어를 고른다",
             "부수 단어(파일 업로드·검색)보다 작업 목적을 먼저 본다",
             "비용 예산과 출력 상한을 함께 건다"],
            "라우팅 배선", "agent_setup/router.py",
            ["분류는 규칙 기반이다. 학습된 라우터가 아니라 조건표에 가깝다.",
             "구성한 반례 테스트는 회귀 검증이지 실사용 오류율 추정이 아니다.",
             "오분류가 나면 상위 티어로 올리는 안전장치를 함께 둔다."]),
      slide("두 정책을 섞지 않는다", "라우팅 · 리워크 · 워크플로 컨트롤",
            ["라우팅: 요청 한 건을 어느 티어로 보낼지 고른다",
             "리워크: 같은 일을 다시 시키는 구간을 관리한다",
             "워크플로 컨트롤: 앞의 둘을 포함하는 상위 개념"],
            "정책 구분", "agent_setup/antigravity/AGENTS.md",
            ["셋을 섞어 부르면 처방도 섞인다. 발표·회의에서 용어를 먼저 통일한다.",
             "라우팅은 단가표, 리워크는 대화 이력 누적, 워크플로는 단계 배치가 대상이다.",
             "효과를 말할 때는 어떤 정책의 값인지 명시한다."]),
      slide("사다리 A · 내부 실패가 올린다", "테스트가 실패하면 턴 안에서 올린다",
            ["수용 기준(AC)이 없으면 올릴 근거도 없다",
             "같은 실패가 반복될수록 누적 비용이 커진다",
             "진단과 적용을 같은 함수로 계산한다"],
            "정책 A", "agent_setup/router.py",
            ["검출할 AC가 부실하면 A가 실패를 놓친다. 그래서 AC를 코드로 강제한다.",
             "respec(다시 스펙)은 실행을 멈추는 무료 경로이고, 실행 비용만 청구된다.",
             "이 정책의 값은 회귀 테스트로 고정한다. 실제 품질 효과는 미측정이다."]),
      slide("사다리 B · 사용자 반려가 올린다", "저장 발화 6턴에서 3회 에스컬레이션",
            ["같은 의도의 반복을 감지해 올린다",
             "스펙 변경·신규 작업은 '반려'가 아니다",
             "분류 신호가 없으면 올리지 않고 되묻는다"],
            "정책 B (로그 재생)", "analysis/replay_logs.py",
            ["과거 '0/5 → 4/5'로 소개했던 수치는 원자료가 없어 철회했다. 지금 값은 저장 발화 재생 결과다.",
             "재생은 가정 없는 재현이지만 표본이 짧다(6턴). 분류 정확도를 보장하지 않는다.",
             "분류가 애매하면 escalate가 아니라 질문을 반환하도록 설계했다."]),
      slide("상태를 작업별로 분리한다", "새 작업은 새 상태로 시작",
            ["task_id별로 의도 이력·시도 횟수·범위를 추적한다",
             "앞 작업의 반려 상태가 새 작업으로 새지 않는다",
             "초기화 전 내부 호출은 명시적 오류로 처리"],
            "상태 관리", "agent_setup/orchestrator.py",
            ["이 부분이 없으면 '새 작업인데 이전 작업의 리워크로 판정'되는 오작동이 생긴다.",
             "회귀 테스트로 새 작업·동일 문구·교차 작업을 검증한다.",
             "로그에 task_id와 판정 근거를 남겨 사후 추적이 가능하게 했다."]),
      slide("진단과 적용은 같은 함수로 계산한다", "$0.05875 (같은 단계·같은 가정)",
            ["범위 · 리셋 · 출력 상한 · 진단/적용을 한 곳에서 계산",
             "두 경로가 같은 값을 내는지 테스트로 고정",
             "티어 단가와 고정 입력 예산은 시나리오 값"],
            "비용 회귀", "agent_setup/router.py · tests/",
            ["두 경로(진단 후 적용 / 곧바로 적용)에서 같은 값이 나오지 않으면 정책 비교가 무의미해진다.",
             "단가는 실제 계약이 아니라 명시적 시나리오다. 실제 전달문 비용은 usage로 측정한다.",
             "이 값은 회귀 테스트의 기준값이며 절감 실적이 아니다."]),
      slide("입력 증가분을 두 번 더하지 않는다", "4,700을 한 번만 더한다",
            ["증가분은 직전 출력과 사용자 발화를 포함한 총량",
             "출력 토큰을 다시 더하면 이중 계상이 된다",
             "누적 예: 1,419 → 6,119 → 10,819"],
            "비용 산식", "analysis/calibrate_growth.py",
            ["이중 계상은 비용을 부풀려 절감을 과장하는 대표적 실수다.",
             "4,700은 페르소나 시나리오를 맞춘 값이지 독립 실측 캘리브레이션이 아니다. 동일 자료 내부 정합만 확인했다.",
             "역산 오차는 0.147%이고, 이 수치는 문서에 한계와 함께 남긴다."]),
      slide("고정 접두부를 캐시에 태운다", "규약·시스템 프롬프트는 매 턴 그대로",
            ["툴 정의와 규약 파일을 맨 앞 고정 블록으로 모은다",
             "변하는 값(사용자 입력·타임스탬프)은 뒤로 보낸다",
             "적중률을 대시보드로 본다"],
            "캐싱 배선", "agent_setup/config.py",
            ["에이전트는 같은 접두부를 매 턴 다시 보낸다. 캐시의 이득이 가장 큰 워크로드다.",
             "최소 길이 미달이면 할인 가정을 하지 않는다. 모델별 조건을 pricing에 모아 두었다.",
             "프롬프트를 자주 바꾸면 캐시가 깨진다. 변경 주기를 정하고 측정한다."]),
      slide("웹 세션으로 넘기는 경로", "구독제 경로는 증분 API 비용 0으로 모델링",
            ["조사·정리는 웹 세션에서, 코드는 API에서",
             "옮겨 붙일 때 수용 기준 형식을 그대로 쓴다",
             "이 경로의 증분 종량 비용은 0으로 모델링한다"],
            "경로 분리", "lab/pricing.py TIER_SCENARIOS",
            ["EXTERNAL=0은 '추가 종량 API 금액이 0'이라는 모델링 선택이다. 총비용이 0이라는 뜻이 아니다.",
             "약관·품질·재현성은 별도로 확인해야 한다. 라우터가 이를 보증하지 않는다.",
             "사람의 검토 시간과 구독료는 이 계산 밖이다.",
             "복사·정리 단계에서 스펙 형식을 고정하면 다음 단계 입력이 줄어든다."]),
      slide("적용 순서와 측정 루프", "켜고 → 재고 → 고친다",
            ["되돌리기 쉬운 것부터 켠다 (캐시 · effort · 배치)",
             "적중률·reasoning 비율·턴 수를 주간으로 본다",
             "절감률 목표가 아니라 품질 게이트를 먼저 정한다"],
            "운영", "agent_setup/antigravity/AGENTS.md · docs/CORRECTIONS.md",
            ["자동화의 목적은 사람을 빼는 것이 아니라 기본값을 낮추는 것이다.",
             "측정 없는 자동화는 조용히 손해를 만들 수 있다(미스 캐싱이 대표적이다).",
             "이상 징후가 보이면 티어를 고정해 비교하는 폴백을 둔다."]),
      slide("마무리 · 오늘 붙일 것 하나", "라우터 한 줄, 캐시 한 블록",
            ["규약 파일을 프리픽스로 고정한다",
             "기본 티어를 한 단계 낮추고 실패 시 올린다",
             "다음 주에 같은 작업의 비용을 다시 잰다"],
            "마무리", "github.com/giyeop-cody/token-cost-lab",
            ["두 가지 모두 설정 수준에서 시작할 수 있고 되돌리기 쉽다.",
             "효과는 자기 로그에서 확인한다. 이 저장소의 값은 출발점이다.",
             "질문·재현 결과는 저장소 이슈로 남기면 다음 사람이 같은 실수를 반복하지 않는다."]),
    ]
    agent = [agent_intro, A[2], A[3], A[16], A[17], agent_extra[0], agent_extra[1], agent_extra[2],
             agent_extra[3], A[21], agent_extra[4], agent_extra[5], agent_extra[6], agent_extra[7],
             A[10], A[11], A[12], A[14], A[23], agent_extra[8], agent_extra[9], agent_extra[10]]
    assert len(agent) == 22

    case_deck = [
      slide("같은 목표, 두 가지 과정", "카페 랜딩 한 페이지",
            ["한 문장 지시(Vibe) vs 4필드 스펙(Spec), 같은 목표",
             "화면은 거의 같고, 청구서와 검사 결과가 다르다",
             "무엇이 비용을 움직였는지 하나씩 본다"],
            "CASE / 2026-09-20", "demo/vibe_vs_spec/README.md",
            ["같은 목표를 두 방식으로 만들어 무엇이 달라졌는지 보는 사례다.",
             "결과물 2개·표본 1쌍이고 청구 usage는 세션 추정치다. 그래서 일반화하지 않는다.",
             "품질 동등성 실험이 아니라는 점을 시작에서 밝힌다."]),
      A[26],
      slide("두 산출물의 첫 화면", "같은 목표, 다른 생성 과정",
            ["두 장 모두 실제 생성 HTML을 Chromium 1280px에서 캡처",
             "다른 점은 토큰 구조와 검사 결과에 있다"],
            "산출물 스크린샷", f"{shots}/vibe_top.png · {shots}/spec_top.png",
            ["첫 화면만 보면 구분이 어렵다. 그래서 토큰과 검사 결과로 내려간다.",
             "디자인 선호도는 검증 대상이 아니다.",
             "캡처는 로컬 Chromium 렌더링 결과이며 발표장 기기 렌더링과 다를 수 있다.",
             "보이는 화면이 비슷하다고 품질 동등성의 증거가 되지는 않는다."],
            images=[(f"{shots}/vibe_top.png", "위: Vibe 산출물 첫 화면 (1280px)"),
                    (f"{shots}/spec_top.png", "아래: Spec 산출물 첫 화면 (1280px)")]),
      slide("전체 페이지 길이 비교", "세로로 긴 한 페이지, 두 산출물",
            ["원본 캡처 두 장을 같은 높이로 축소해 나란히 붙였다",
             "구성 요소 수와 배치가 비슷한지 눈으로 확인한다"],
            "전체 페이지 축소 비교", f"{shots}/vibe_full.png · {shots}/spec_full.png",
            ["구성 요소 수와 배치가 비슷한지 눈으로 확인하는 자료다.",
             "축소본이라 세부 텍스트는 원본 PNG를 봐야 한다.",
             "이 그림으로 품질 우열을 말하지 않는다. 스크롤 길이는 비용·품질 판정이 아니다."],
            images=[(f"{shots}/vibe_spec_full_2up.png", "왼쪽 Vibe 전체 페이지 · 오른쪽 Spec 전체 페이지 (축소)")]),
      slide("모바일 390px에서도 같은 1열", "정적 문자열이 아니라 실제 렌더링",
            ["문자열 검사만으로는 2열로 바뀌어도 통과한다",
             "아래 그림은 현재 Spec 산출물을 390px에서 캡처한 것"],
            "반응형 스크린샷", f"{shots}/spec_mobile.png",
            ["모바일 대응은 '미디어쿼리 문자열이 있는가'로 확인하면 안 된다는 사례다.",
             "실제 렌더링된 그리드 열 수를 브라우저에서 확인한다.",
             "브라우저가 없으면 검사는 UNVERIFIED로 끝난다."],
            images=[(f"{shots}/spec_mobile.png", "Spec 산출물 · 390×844 캡처")]),
      A[27],
      slide("입력이 늘고 비싼 출력이 줄었다", "증가 666 · 감소 680 · 증가 156",
            ["이 케이스에서 input과 cache는 서로 겹치지 않는 버킷으로 정의",
             "합계는 7,868 → 8,010 (증가 1.8%)"],
            "추정치 재계산", "demo/vibe_vs_spec/usage.json",
            ["벤더 usage 필드 이름과 동일하다고 가정하면 이중 계상할 수 있다.",
             "추론 토큰은 출력 요율로 과금된다는 가정을 쓴다.",
             "표의 값은 모두 추정치이며 실제 청구서가 아니다."],
            facts=[("비캐시 입력", "486 → 1,152  (증가 666)"),
                   ("추론+보이는 출력", "7,070 → 6,390  (감소 680)"),
                   ("캐시 입력(추정)", "312 → 468  (증가 156)"),
                   ("합계", "7,868 → 8,010  (증가 1.8%)")]),
      slide("세 단가로 같은 추정치를 환산", "8.3% / 7.6% / 8.1% 비용 감소",
            ["같은 추정 토큰을 세 단가로 환산한 표",
             "모델을 바꿔도 방향은 같다"],
            "단가별 비용 재계산", "presentation/case_vibe_vs_spec/cost_comparison.md",
            ["단가가 바뀌어도 결론의 방향이 유지되는지 확인하려는 계산이다.",
             "캐시를 전부 신규 입력으로 환산한 8.1%가 가장 보수적인 값이다.",
             "세 값 모두 추정 usage의 산술이고 캐시 적격성은 확인하지 않았다."],
            facts=[("GPT-5 · 캐시 $0.125/M", "$0.0713465 → $0.0653985  (8.3% 감소)"),
                   ("Claude Sonnet 4.6 · 캐시 0.1×", "$0.1076016 → $0.0994464  (7.6% 감소)"),
                   ("GPT-5 · 캐시 전부 미적용", "$0.0716975 → $0.0659250  (8.1% 감소)")]),
      A[29],
      slide("단가비가 손익을 결정한다", "r > (666 + 156h) / 680",
            ["r = 출력/입력 단가, h = 캐시 읽기/입력 단가",
             "출력 단가가 조금만 높아도 스펙 쪽이 유리해진다"],
            "단가 민감도", "demo/vibe_vs_spec/sensitivity.py",
            ["모든 가격 체계에서 항상 이긴다는 뜻이 아니라, 이 토큰 이동에서의 조건이다.",
             "DeepSeek처럼 캐시 할인이 더 깊은 모델은 손익분기가 달라진다.",
             "실제 청구서 대조는 하지 않았다."],
            facts=[("손익분기 조건", "r > (666 + 156h) / 680"), ("h = 0.1이면", "r = 1.0024"),
                   ("r → ∞ 수렴", "약 9.62% 감소에 수렴"), ("실제 청구서", "미확인 (usage 추정치 산술)")]),
      slide("무엇을 확인했나", "정적 16 + 브라우저 29항목",
            ["390 · 820 · 821 · 1280px 렌더링과 앵커 이동 검사",
             "실패하는 변조를 넣어 검사가 실제로 잡는지도 확인"],
            "실동작 검사 (Chromium)", "demo/vibe_vs_spec/verify_ac.py",
            ["검사 항목은 산출물의 요구사항(수용 기준)에 맞춰 정의했다.",
             "검사를 통과했다는 것이 두 생성 과정의 품질 동등성을 뜻하지는 않는다.",
             "검사 항목 수는 실행 로그에서 확인한다."]),
      slide("그 네 칸에 무엇을 적는가", "한 줄이면 충분한 결정 네 개",
            ["페이지 — 섹션과 순서를 고정한다 (이번엔 히어로·메뉴·지도·리뷰·CTA)",
             "스택 — 생성 방식과 파일 구성을 정한다 (단일 HTML + CSS, JS 없음)",
             "디자인 — 톤·색·타이포 기준을 한 줄로 (따뜻한 크림 톤, 사진 대신 일러스트)",
             "수용 기준 — 검사 가능한 문장으로 (390px에서 1열, 앵커 이동, JS 오류 0)"],
            "스펙 템플릿", "demo/vibe_vs_spec/EXPERIMENT_A_PROTOCOL.md",
            ["네 칸은 이 사례에서 실제로 쓴 스펙의 구성이다. 각 칸은 결정 하나를 요구한다.",
             "수용 기준은 나중에 검사 스크립트로 그대로 옮길 수 있어야 한다. '예쁘게'는 기준이 아니다.",
             "이 템플릿의 효과는 아직 사전 등록된 다수 과제 A/B로 검증하지 않았다. 프로토콜은 저장소에 공개해 두었다.",
             "이 사례의 목적은 '스펙을 쓰면 8% 싸다'가 아니라 '결정을 먼저 적으면 되돌림이 줄어든다'를 보이는 것이다."]),
      slide("다음 프로젝트에서 할 일", "결정 네 개를 먼저 적는다",
            ["페이지 · 스택 · 디자인 · 수용 기준",
             "설명 대신 결정을 적고, 수용 기준을 코드로 옮긴다",
             "완료 후 재작업 횟수와 총비용을 기록한다"],
            "적용", "demo/vibe_vs_spec/README.md",
            ["네 필드는 이 사례에서 실제로 쓴 스펙의 구성이다.",
             "스펙을 길게 쓰라는 뜻이 아니다 — 결정만 담으면 4,000토큰 이하로 충분하다.",
             "재작업 횟수를 기록해 두면 다음 사례에서 인과를 말할 수 있다."]),
      slide("재현", "python demo/vibe_vs_spec/verify_ac.py",
            ["이미지 · usage 추정치 · 검사 스크립트가 저장소에 있다",
             "브라우저가 없으면 UNVERIFIED로 종료한다",
             "덱과 대본도 같은 원천에서 생성된다"],
            "재현", "demo/vibe_vs_spec/",
            ["터미널에서 같은 검사를 다시 돌릴 수 있다.",
             "비교 이미지를 다시 만들려면 슬라이드에 적힌 생성 스크립트를 쓴다.",
             "숫자를 손으로 고치면 검증이 실패한다."]),
      slide("마무리", "스펙은 짧게, 결정만",
            ["서론 대신 페이지 · 스택 · 디자인 · 수용 기준",
             "되돌림이 줄면 턴 수가 줄고 비용도 줄어든다",
             "다음 사례는 다수 과제 A/B로 검증한다"],
            "마무리", "demo/vibe_vs_spec/README.md",
            ["이 사례에서 확실한 것은 토큰 구조가 '싼 입력↑, 비싼 출력↓'로 이동했다는 점이다.",
             "그 이동이 곧 품질 보장은 아니다. 함께 측정해야 한다.",
             "다음 단계는 사전 등록된 A/B다."]),
    ]
    assert len(case_deck) == 15

    return {"token_cost": A, "token_cost_main": token_cost_main, "token_cost_bonus": bonus,
            "token_cost_agent": agent, "case_vibe_vs_spec/vibe_vs_spec": case_deck}


def notes_text(spec):
    """발표자 노트 — 렌더러와 검증기가 같은 함수를 쓴다(이중 구현 금지)."""
    return "\n".join([*spec["script"], *[f"{a}: {b}" for a, b in spec["facts"]],
                      *[f"그림: {c} ({a})" for a, c in spec["images"]],
                      f"근거: {spec['source']}", f"증거 범위: {spec['scope']}"])


def expected_texts(spec, index):
    return [f"TOKEN COST LAB  /  {index:02d}", spec["scope"], spec["title"], spec["hero"],
            *spec["lines"], *[cell for row in spec["facts"] for cell in row],
            *([spec["chart"]["caption"]] if spec.get("chart") else [caption for _, caption in spec["images"]]),
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
    prs.core_properties.subject = "Cost-saving talk, 2026-09-20"
    prs.core_properties.author = "token-cost-lab"
    prs.core_properties.keywords = "speaker notes carry scope and limits; see docs/CORRECTIONS.md"
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
        is_chart = bool(spec.get("chart"))
        text(texts[0], "index", .7,.3,5,.3,11,"93A4B5")
        text(texts[1], "scope", 6.3,.3,6.3,.3,11,"36D399")
        text(texts[2], "title", .7,.62 if is_chart else .9,11.9,.9,29,bold=True)
        narrow = bool(spec["images"] or spec["facts"])
        hero_size = 24 if len(spec["hero"]) > 34 else 29
        hero_y = 1.38 if is_chart else 1.95
        text(texts[3], "hero", .7,hero_y,11.9 if not narrow else 7.2,.85,hero_size,"36D399",True)
        for j, line in enumerate(spec["lines"]):
            y = (2.22 + j*.56) if is_chart else (3.13 + j*.70)
            width = 11.65 if (is_chart or not narrow) else 7.0
            text(line, f"body-{j}", .85, y, width, .67, 17.5)
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
        if is_chart:
            # 그래프는 전폭. 메시지 블록 아래, 캡션은 그림 바로 밑.
            from PIL import Image
            box_w, top, bottom = 11.65, 3.34, 6.68
            with Image.open(ROOT / spec["chart"]["file"]) as im:
                w, h, dx, dy = fit(box_w, bottom - top, *im.size)
            sl.shapes.add_picture(str(ROOT / spec["chart"]["file"]), Inches(.85 + dx),
                                  Inches(top + dy), Inches(w), Inches(h))
            text(spec["chart"]["caption"], "chart-caption", .85, bottom + .03, box_w, .26, 9.5, "93A4B5")
            text(spec["source"], "source", .85,6.98,12,.30,10,"93A4B5")
            text(texts[-1], "footer", .85,7.20,12,.28,10,"93A4B5")
        else:
            text(spec["source"], "source", .7,6.65,12,.30,10,"93A4B5")
            text(texts[-1], "footer", .7,7.02,12,.28,10,"93A4B5")
        sl.notes_slide.notes_text_frame.text = notes_text(spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(path)


def script_text(specs):
    content = (f"# {specs[0]['title']} — 발표 대본\n\n"
               f"{len(specs)}장 · 약 30분 · 2026-09-20 · 생성 원천: "
               f"`presentation/deckgen/build_verified.py`와 원자료.\n\n"
               "슬라이드에는 메시지와 숫자만 두고, 검증 범위·한계·질문 대비는 이 대본에 적는다.\n\n")
    for i, spec in enumerate(specs, 1):
        content += f"## {i}. {spec['title']}\n\n**{spec['hero']}** · {spec['scope']}\n\n"
        content += "\n".join("- " + t for t in spec["lines"]) + "\n\n"
        content += "**멘트**\n\n" + "\n\n".join(spec["script"]) + "\n\n"
        if spec["facts"]:
            content += "\n".join(f"| {a} | {b} |" for a, b in spec["facts"]) + "\n\n"
        if spec["images"]:
            content += "\n".join(f"![{c}](../{a})" for a, c in spec["images"]) + "\n\n"
        content += f"근거: `{spec['source']}` · 증거 범위: {spec['scope']}\n\n"
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
