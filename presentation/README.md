# 발표 자료 — 발표체 재작성판 (2026-09-21)

**슬라이드에는 메시지와 숫자만** 둡니다. 검증 범위·한계·반례·질문 대비는 **발표자 노트**로 내려
같은 대본(`script*.md`)으로도 읽을 수 있게 했습니다. 각 덱은 **약 30분 발표 분량**(장당 1분 안팎)으로
구성했습니다. 핵심 원칙은 유지하고 실측 / 로그 재계산 / 외부 연구 / 시나리오 / 소프트웨어 테스트를
발표자 노트에서 구분합니다. 현재 `main`에는 코드와 발표 산출물이 함께 있습니다.

| 덱 | PPTX / PDF | 대본 |
|---|---|---|
| 통합 29장 (약 30분) | [PPTX](token_cost.pptx) · [PDF](token_cost.pdf) | [대본](script.md) |
| 본편 22장 (약 30분) | [PPTX](token_cost_main.pptx) · [PDF](token_cost_main.pdf) | [대본](script_main.md) |
| 보너스 10장 (약 30분) | [PPTX](token_cost_bonus.pptx) · [PDF](token_cost_bonus.pdf) | [대본](script_bonus.md) |
| 에이전트 18장 (약 30분) | [PPTX](token_cost_agent.pptx) · [PDF](token_cost_agent.pdf) | [대본](script_agent.md) |
| 카페 케이스 13장 | [PPTX](case_vibe_vs_spec/vibe_vs_spec.pptx) · [PDF](case_vibe_vs_spec/vibe_vs_spec.pdf) | [대본](case_vibe_vs_spec/script_case.md) |

## 수정·검증

숫자와 조건은 `lab/evidence.py`에서 원자료를 읽어 계산하고,
`presentation/deckgen/build_verified.py` 하나에서 모든 덱·대본을 생성합니다.
기존 디자인의 짙은 배경·초록 강조는 유지하고, 오해를 줄이도록 문안을 다시 구성했습니다.

```bash
pip install -r requirements-dev.txt
python tools/reproduce_audit.py
python tools/verify_deck.py
# Linux 예: sudo apt-get install libreoffice-impress fonts-nanum
python presentation/deckgen/make_pdf.py --check
```

검증기는 실제 PPTX의 **모든 텍스트·수치·비교 조건**을 재생성된 명세와 대조합니다.
`240→999` 같은 변조는 실패합니다. PDF는 실제 페이지 수·추출 텍스트까지 대조합니다.
텍스트 박스 경계 검사는 시각적 완벽성이나 외부 사실의 참을 보증하지 않습니다.
PDF 일부 페이지는 로컬 렌더링으로 확인했지만 발표장 기기에서는 아직 시험하지 않았습니다.

## 발표자가 지켜야 할 구분

- 240배는 **기존 $1.25/$10 환산**, 공식 Standard는 약 199배. 비교는 **자동/미지정**.
- 미지정 6/6과 명시적 0의 5/6을 섞지 않기. ‘같은 정확도’보다 ‘허용오차 통과 횟수가 같음’.
- 문자당 비용을 ‘동일 의미량’으로 읽지 않기. 사고 토큰을 ‘더 깊은 추론’의 자체 증거로 읽지 않기.
- 20.8배·SDD 71%·리플레이 배수를 실제 품질 동등 정책 A/B의 성과로 소개하지 않기.
- 브라우저/mock 테스트를 새 live LLM 측정이라고 부르지 않기.

변경 상세: [CORRECTIONS.md](../docs/CORRECTIONS.md).
수정 전 작업 노트는 [archive/](archive/README.md)에 비현행으로 격리했습니다.
파일명 27개의 원 바이트→ASCII 경로 매핑은 `docs/path_migration.json`에 있습니다.
