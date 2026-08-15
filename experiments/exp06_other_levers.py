# -*- coding: utf-8 -*-
"""
실험 06 — 그 밖의 절감 레버들

다루는 레버:
  A. Batch API            — 입력·출력 50% 할인 (지연 시간을 돈으로 바꾸기)
  B. 프롬프트 압축         — LLMLingua 계열, 압축비 vs 정확도 손실
  C. 시맨틱 캐싱           — 호출 자체를 없애기 (프롬프트 캐싱과 다름)
  D. 모델 라우팅           — 쉬운 질문은 싼 모델로
  E. 스택 적층             — 레버들을 곱했을 때의 총절감

각 레버는 '적용 가능한 워크로드'가 다르다. 무조건 다 켜면 되는 게 아니다.

실행:
  python experiments/exp06_other_levers.py
  python experiments/exp06_other_levers.py --model gpt5 --calls 100000

출처:
  A. Batch API
     Anthropic — https://docs.anthropic.com/en/docs/build-with-claude/batch-processing
       (50% 할인, 최대 24시간, 배치당 10만 요청, 결과 29일 보관)
     OpenAI    — https://platform.openai.com/docs/guides/batch
       (50% 할인, 24시간 SLA, 배치당 5만 요청)
  B. 프롬프트 압축
     Jiang et al., "LLMLingua", EMNLP 2023 — https://arxiv.org/abs/2310.05736
       (최대 20x 압축, 성능 손실 1.5포인트)   <- "20x"의 출처는 여기다
     Jiang et al., "LongLLMLingua" — https://arxiv.org/abs/2310.06839
     Pan et al., "LLMLingua-2", ACL 2024 Findings
       — https://arxiv.org/abs/2403.12968  (압축비 2~5x, 지연 1.6~2.9x 개선)
     주의: 20x를 LLMLingua-2에 귀속시키는 오인용이 흔하다. 두 논문은 다르다.
  C. 시맨틱 캐싱
     Regmi & Pun, "GPT Semantic Cache" — https://arxiv.org/abs/2411.05276
       (API 호출 최대 68.8% 감소, positive hit rate 97%+)
  D. 모델 라우팅
     Ong et al., "RouteLLM", ICLR 2025 — https://arxiv.org/abs/2406.18665
       (비용 2배 이상 절감, 응답 품질 유지)
  전체 목록: ../SOURCES.md
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab import pricing, report  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet", choices=list(pricing.MODELS))
    ap.add_argument("--calls", type=int, default=50_000, help="배치 잡 규모")
    args = ap.parse_args()

    m = pricing.get(args.model)
    N = args.calls

    report.title("실험 06 — 그 밖의 절감 레버들")
    report.kv("모델", m.name)

    # ── A ──────────────────────────────────────────────
    report.section("A. Batch API — 지연 시간을 할인으로 바꾸기")
    inp, out = 2_000, 500
    sync = pricing.cost(m, inp, out) * N
    batch = pricing.cost(m, inp, out, batch=True) * N
    report.kv("잡 규모", f"{N:,}건 x (입력 {inp:,} / 출력 {out:,})")
    report.kv("동기 호출", pricing.usd(sync, 2))
    report.kv("Batch API", pricing.usd(batch, 2), f"절감 {(1-batch/sync)*100:.0f}%")
    report.table(
        ["항목", "OpenAI Batch", "Anthropic Message Batches"],
        [["할인", "입력·출력 50%", "입력·출력 50%"],
         ["SLA", "24시간 내", "24시간 내 (실측 대개 1시간 이내)"],
         ["배치당 최대", "50,000건 / 200MB JSONL", "10,000건 이상 (문서 기준 상이)"],
         ["스트리밍", "불가", "불가"],
         ["캐싱 병용", "가능", "가능 (할인 중첩)"]],
    )
    print("  적합: 야간 평가(eval), 대량 분류/태깅, 문서 일괄 처리, 리포트 생성,")
    print("        레포 전체 테스트 생성, 대규모 리팩터링 사전 분석")
    print("  부적합: 대화형 UI, 실시간 코딩 에이전트, 사용자 대기 화면이 있는 모든 것")
    print("  → 토큰 수는 그대로다. '가격'만 반값이 된다. 리스크가 사실상 없는 레버.")

    # ── B ──────────────────────────────────────────────
    report.section("B. 프롬프트 압축 — 보낼 내용을 미리 줄이기")
    print("  LLMLingua 계열은 작은 모델로 중요도가 낮은 토큰을 골라 지운다.")
    ctx = 20_000
    rows = []
    for ratio, loss in [(1, "0%"), (2, "1% 미만"), (5, "1~3%"),
                        (10, "3~7%"), (20, "5~15%"), (30, "급격히 악화")]:
        t = int(ctx / ratio)
        c = t * m.inp / 1e6
        rows.append([f"{ratio}x", f"{t:,}", pricing.usd(c),
                     f"{(1-1/ratio)*100:.0f}%", loss])
    report.table(["압축비", "입력tok", "요청당 입력비용", "절감", "정확도 손실(보고치)"],
                 rows, ["r", "r", "r", "r", "l"])
    print("  · LLMLingua: 최대 20배 압축에 성능 손실 2% 미만 (GSM8K/BBH/CoQA 등)")
    print("  · LongLLMLingua: 4배 압축에서 오히려 정확도 +17~21%p")
    print("    (lost-in-the-middle 현상이 완화되기 때문)")
    print("  · LLMLingua-2: 같은 압축비에서 v1을 넘고, 압축 자체가 3~6배 빠름")
    report.table(
        ["콘텐츠 종류", "보존 권장", "이유"],
        [["지시·제약·수용조건", "80~90%", "지우면 요구사항이 바뀐다"],
         ["few-shot 예시", "40~60%", "패턴만 남으면 충분"],
         ["검색된 RAG 컨텍스트", "20~40%", "질의 대비 60~80%가 중복"],
         ["코드 구문·수식·ID", "100% (압축 금지)", "한 글자만 틀려도 깨진다"]],
    )
    print("  ⚠️ 압축기를 돌리는 비용과 지연도 계산에 넣어야 한다.")
    print("     짧은 프롬프트에는 이득이 없다. 긴 RAG 컨텍스트에서만 켜라.")
    print("  💡 도구 없이도 된다: 중복 문단 제거·표 정규화만 해도 20~40% 감소.")

    # ── C ──────────────────────────────────────────────
    report.section("C. 시맨틱 캐싱 — 호출 자체를 없애기")
    print("  프롬프트 캐싱과 다르다. 프롬프트 캐싱은 '호출당 비용'을 낮추고,")
    print("  시맨틱 캐싱은 '호출 자체'를 제거한다. 둘은 같이 쓸 수 있다.")
    per_call = pricing.cost(m, 3_000, 700)
    monthly = 100_000
    rows = []
    for hr, label in [(0.0, "없음"), (0.20, "보수적 (일반 워크로드)"),
                      (0.45, "현실 상한 (반복 많은 워크로드)"),
                      (0.65, "논문 보고치 (GPT Semantic Cache)"),
                      (0.86, "AWS 공개 평가 사례")]:
        c = per_call * monthly * (1 - hr)
        rows.append([label, f"{hr*100:.0f}%", pricing.usd(c, 2),
                     f"{hr*100:.0f}%"])
    report.table([f"히트율 시나리오 ({monthly:,}콜/월)", "히트율", "월 비용", "절감"],
                 rows, ["l", "r", "r", "r"])
    print("  · 프로덕션 현실 히트율: 20~45%. 고반복 워크로드에서 40~70%.")
    print("  · AWS 공개 평가(실제 챗봇 쿼리 63,796건): 비용 86%↓, 지연 88%↓, 정확도 91%+ 유지")
    print("  · 논문(GPT Semantic Cache): API 호출 최대 68.8% 감소, 유사도 임계값 0.8이 최적")
    print("  ⚠️ 위험: 임계값이 느슨하면 '비슷하지만 틀린 답'을 준다.")
    print("     개인화/실시간 데이터가 섞인 응답은 캐싱 금지. 멀티턴은 키에 컨텍스트를 포함해야 한다.")

    # ── D ──────────────────────────────────────────────
    report.section("D. 모델 라우팅 — 쉬운 질문에 비싼 모델을 쓰지 않기")
    strong, weak = pricing.get("opus"), pricing.get("deepseek")
    ci, co = 3_000, 800
    rows = []
    for share, label in [(1.00, "전부 강 모델"), (0.50, "절반 라우팅"),
                         (0.14, "RouteLLM 보고치 (강 모델 14%)"),
                         (0.05, "공격적 라우팅")]:
        c = (share * pricing.cost(strong, ci, co)
             + (1 - share) * pricing.cost(weak, ci, co)) * 10_000
        rows.append([label, f"{share*100:.0f}%", pricing.usd(c, 2),
                     f"{(1-c/(pricing.cost(strong,ci,co)*10_000))*100:.0f}%"])
    report.table(["전략 (10,000콜)", "강 모델 비중", "총비용", "절감"],
                 rows, ["l", "r", "r", "r"])
    report.table(
        ["방식", "보고된 절감", "출처/조건"],
        [["학습된 라우터", "45~85%", "RouteLLM: MT-Bench 85%↓, GPT-4 품질 95% 유지"],
         ["캐스케이드", "50~98%", "FrugalGPT: 싼 모델 먼저, 실패 시 승급"],
         ["시맨틱 라우터", "가변", "vLLM SR: 정확도 +10.2%p, 지연 -47%, 토큰 -48.5%"],
         ["매니지드", "최대 30%", "Bedrock Intelligent Prompt Routing"]],
    )
    print("  ⚠️ 함정: 벤치마크에서 잡은 임계값을 프로덕션에 그대로 쓰면 절감이 과대 추정된다.")
    print("     순서: (1) 품질 측정 도구 먼저 → (2) 규칙 기반 라우팅으로 시작")
    print("           → (3) 임계값 주기적 재보정. 저볼륨에서는 라우팅 오버헤드가 절감을 상쇄한다.")

    # ── E ──────────────────────────────────────────────
    report.section("E. 스택 적층 — 레버는 곱해진다")
    layers = [
        ("시맨틱 캐싱 (호출 30% 제거)", 0.30),
        ("모델 라우팅 (남은 것의 40% 절감)", 0.40),
        ("프롬프트 캐싱 (남은 것의 50% 절감)", 0.50),
        ("verbosity·effort 튜닝 (남은 것의 25% 절감)", 0.25),
        ("배치 가능한 20%를 반값으로 (10% 절감)", 0.10),
    ]
    remaining = 1.0
    rows = []
    for label, cut in layers:
        before = remaining
        remaining *= (1 - cut)
        rows.append([label, f"{before*100:.0f}%", f"{remaining*100:.0f}%",
                     f"-{(before-remaining)*100:.0f}%p"])
    report.table(["레버 (순서대로 적용)", "적용 전", "적용 후", "기여"],
                 rows, ["l", "r", "r", "r"])
    report.kv("최종 남은 비용", f"{remaining*100:.0f}%",
              f"→ 총 {(1-remaining)*100:.0f}% 절감")
    print("  업계 보고 범위(전체 스택 적용 시 60~80% 절감)와 일치한다.")
    print("  ⚠️ 다만 이건 상한선이다. 각 레버의 절감률은 워크로드에 따라 크게 흔들린다.")
    print("     반드시 자기 데이터로 A/B를 돌린 뒤 숫자를 확정할 것.")

    report.section("F. 적용 우선순위 — 노력 대비 효과")
    report.table(
        ["순위", "레버", "난이도", "리스크", "먼저 볼 조건"],
        [["1", "프롬프트 캐싱", "낮음", "없음", "고정 프리픽스 1K tok 이상"],
         ["2", "verbosity / effort", "낮음", "낮음", "설정 한 줄로 끝나는 경우가 많음"],
         ["3", "Batch API", "낮음", "없음", "지연에 둔감한 잡이 있는가"],
         ["4", "스펙 먼저 (SDD)", "중간", "낮음", "재작업 사이클이 3회 이상인가"],
         ["5", "컨텍스트 컴팩션", "중간", "중간", "세션이 20턴을 넘는가"],
         ["6", "모델 라우팅", "높음", "중간", "품질 측정 도구가 이미 있는가"],
         ["7", "시맨틱 캐싱", "높음", "높음", "질의 반복률이 20%를 넘는가"],
         ["8", "프롬프트 압축", "높음", "중간", "RAG 컨텍스트가 10K tok을 넘는가"]],
    )
    print("  1~3번은 오늘 오후에 켤 수 있고 되돌리기도 쉽다. 여기서 시작하라.")


if __name__ == "__main__":
    main()
    report.doc_sources(__doc__)
