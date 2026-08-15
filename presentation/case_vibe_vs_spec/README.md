# 발표 패키지 — Vibe vs Spec 토큰·비용 비교

`demo/vibe_vs_spec/` 케이스 스터디의 발표 산출물.
main은 "수치를 재현하는 코드만 담는다"는 저장소 원칙에 따라
발표 자료는 이 `presentation` 브랜치의 `presentation/case_vibe_vs_spec/` 에 둔다.
본 발표 자료(29장 덱·대본)는 상위 `presentation/` 폴더 참고.

## 내용

| 파일 | 설명 |
|---|---|
| `Vibe-vs-Spec_토큰비용_리포트.pptx` | 9장 슬라이드 덱 (과정 → 스크린샷 → 토큰 → 비용 → 분석 → 결론) |
| `케이스_비교_리포트.md` | 산출물·토큰 비교 상세 |
| `토큰_가격_비교.md` | Claude/GPT-5 단가 적용 비용 계산 (주의: 이 문서의 -8.5%는 반올림 오차, 정확값은 -8.3%) |
| `세션_기록.md` | Vibe 세션 원본 기록 |

## 수치 원자료

모든 수치의 원자료와 재검증 스크립트는 main 브랜치
[`demo/vibe_vs_spec/`](../../tree/main/demo/vibe_vs_spec)에 있다
(usage.json · verify_ac.py · transcripts).
