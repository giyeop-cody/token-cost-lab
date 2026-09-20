# Vibe vs Spec — 정정판 대본

12장 · 2026-09-20 · 생성 원천: `presentation/deckgen/build_verified.py`와 원자료.

## 1. Vibe vs Spec

**같은 목표 페이지, 추정 usage 비교** · CASE / 정정판

- 카페 랜딩 · 생성 산출물 2개 · 표본 1쌍
- 실제 청구 usage나 무작위 배정된 SDD 실험이 아니다.

근거: `demo/vibe_vs_spec/README.md`

## 2. 카페 케이스: 절감 관측의 증거 수준

**usage 추정치 환산 -8.3%** · 추정 usage의 비용 재계산

- 고정 usage 추정치 + GPT-5 단가: $0.07135 → $0.06540
- 토큰 합계 7,868 → 8,010 (+1.8%). 실제 청구 usage가 아니라 세션 추정치다.
- 캐시 적격성 미확인. 모든 추정 입력을 신규 입력으로 환산하면 -8.1%.
- Spec은 Vibe 결과를 역산. 백지 스펙 비용·재작업 감소·품질 동등성을 검증한 것은 아니다.

근거: `demo/vibe_vs_spec/usage.json · verify_ac.py`

## 3. 두 산출물의 첫 화면

**같은 목표, 다른 생성 과정** · 산출물 스크린샷

- 두 장 모두 실제 생성 HTML을 Chromium 1280px에서 캡처한 화면이다.
- 보이는 화면이 비슷하다는 것이 품질 동등성의 증거는 아니다.

![위: Vibe 산출물 첫 화면 (1280px)](../demo/vibe_vs_spec/shots/vibe_top.png)
![아래: Spec 산출물 첫 화면 (1280px)](../demo/vibe_vs_spec/shots/spec_top.png)

근거: `demo/vibe_vs_spec/shots/vibe_top.png · demo/vibe_vs_spec/shots/spec_top.png`

## 4. 모바일 390px에서도 같은 1열

**정적 문자열이 아니라 실제 렌더링** · 반응형 스크린샷

- 문자열 검사만으로는 2열로 바뀌어도 통과한다.
- 아래 그림은 현재 Spec 산출물을 390px에서 캡처한 것이다.

![Spec 산출물 · 390×844 캡처](../demo/vibe_vs_spec/shots/spec_mobile.png)

근거: `demo/vibe_vs_spec/shots/spec_mobile.png`

## 5. 전체 페이지 길이 비교

**세로로 긴 한 페이지, 두 산출물** · 전체 페이지 축소 비교

- 원본 캡처 1,280×3,400 두 장을 같은 높이로 축소해 나란히 붙였다.
- 스크롤 길이가 비슷하다는 사실은 비용·품질 동등성 판정이 아니다.

![왼쪽 Vibe 전체 페이지 · 오른쪽 Spec 전체 페이지 (축소)](../demo/vibe_vs_spec/shots/vibe_spec_full_2up.png)

근거: `demo/vibe_vs_spec/shots/vibe_full.png · demo/vibe_vs_spec/shots/spec_full.png · demo/vibe_vs_spec/make_fullpage_2up.py`

## 6. 입력이 늘고 비싼 출력이 줄었다

**+666 / -680 / +156** · 추정치 재계산

- 이 케이스에서 input과 cache는 서로 겹치지 않는 버킷으로 정의했다.
- 벤더 usage 필드 이름과 동일하다고 가정하면 이중 계상할 수 있다.

| 비캐시 입력 | 486 → 1,152  (증가 666) |
| 추론+보이는 출력 | 7,070 → 6,390  (감소 680) |
| 캐시 입력(추정) | 312 → 468  (증가 156) |
| 합계 | 7,868 → 8,010  (증가 1.8%) |

근거: `demo/vibe_vs_spec/usage.json`

## 7. 세 단가로 같은 추정치를 환산

**8.3% / 7.6% / 8.1% 비용 감소** · 단가별 비용 재계산

- 토큰은 그대로 두고 단가와 캐시 가정만 바꾼 산술이다.
- 다른 모델을 실행한 실측이 아니며, 캐시 적격성은 미확인이다.

| GPT-5 · 캐시 $0.125/M | $0.0713465 → $0.0653985  (8.3% 감소) |
| Claude Sonnet 4.6 · 캐시 0.1× | $0.1076016 → $0.0994464  (7.6% 감소) |
| GPT-5 · 캐시 전부 미적용 | $0.0716975 → $0.0659250  (8.1% 감소) |

근거: `demo/vibe_vs_spec/cost_comparison.md · verify_case.py`

## 8. 단가비가 손익을 결정한다

**r > (666 + 156h) / 680** · 단가 민감도

- r = 출력/입력 단가, h = 캐시 읽기/입력 단가.
- 모든 가격 체계에서의 보편 법칙이 아니라 고정 토큰 이동의 감도 분석이다.

| 손익분기 조건 | r > (666 + 156h) / 680 |
| h = 0.1이면 | r = 1.0024 |
| r → ∞ 수렴 | 약 9.62% 감소에 수렴 |
| 실제 청구서 | 미확인 (usage 추정치 산술) |

근거: `demo/vibe_vs_spec/sensitivity.py`

## 9. 품질 동등성 대신 실제 AC 범위를 공개

**정적 16항목 + 브라우저 29항목** · 현재 산출물의 실행 검사

- 390/820/821/1280px 그리드·메뉴 표시·가로 스크롤 검사
- 각 카드의 내용과 세 앵커의 실제 스크롤 이동 검사
- 디자인 선호도·모든 사용자 의도·두 생성 과정의 품질 동등성은 검증하지 않는다.

근거: `demo/vibe_vs_spec/verify_ac.py · tools/browser_ac.py`

## 10. 실패하는 반례도 넣는다

**모바일 2열 변조 → FAIL** · 변조 회귀

- CSS에 미디어쿼리 문자열이 있다는 것만으로 1열 전환이 보장되지 않는다.
- 실제 렌더링된 gridTemplateColumns를 확인한다.
- 브라우저가 없으면 PASS가 아니라 UNVERIFIED(exit 2).

근거: `experiments/exp04_agent_loop_sdd.py (--warm-cache = legacy)`

## 11. 반례의 비교 대상을 정확히 읽는다

**SDD 도구 간 비교 ≠ SDD 대 무스펙** · 외부 보고의 범위 제한

- Spec-Kit +97~109%: OpenSpec 대비 두 사례의 외부 블로그 보고. 둘 다 SDD 접근.
- ETH AGENTS.md 연구: 저장소 컨텍스트 파일 조건. 모든 짧은 스펙이 손해라는 실험 아님.
- 짧고 필요한 요구사항만 쓰라는 실무 원칙은 유지하되 효과를 직접 측정한다.

근거: `SOURCES.md §4 · arxiv.org/html/2602.11988v1`

## 12. 다음 실험: 스펙이 재작업을 줄이는가

**사전등록된 품질·비용 비교** · 후속 계획 / 미실행

- 백지 스펙 작성 비용부터 포함하고 다수 과제를 무작위 배정한다.
- 같은 AC·모델·출력 예산·가격·캐시 조건으로 성공률과 총비용을 기록한다.
- 진행하지 않은 실험의 절감률은 결과로 채우지 않는다.

근거: `demo/vibe_vs_spec/EXPERIMENT_A_PROTOCOL.md`
