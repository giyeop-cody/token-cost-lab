# 카페 케이스 발표 — 정정판

[PPTX 15장](vibe_vs_spec.pptx) · [PDF 15쪽](vibe_vs_spec.pdf) · [대본](script_case.md) (약 30분)

근거는 [케이스 설명](../../demo/vibe_vs_spec/README.md)의 **세션 토큰 추정치**입니다.
실제 청구 실측·재작업 감소의 인과 실험으로 소개하지 않습니다.

```bash
python presentation/case_vibe_vs_spec/verify_case.py --with-pdf
python demo/vibe_vs_spec/verify_ac.py
```

첫 명령은 실제 발표파일 정합, 둘째는 현재 HTML의 AC를 검사합니다. 검증 파일이 없으면 실패합니다.
`session_history.md`는 옛 세션 기록이고, 현재 비용/품질 근거의 해석은 상위 정정 보고서를 따릅니다.
