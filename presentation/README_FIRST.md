# 토큰 절약 발표 패키지 (2026-08-15)

| 파일 | 설명 |
|---|---|
| `토큰_절약_발표.pptx` | 발표 덱 **29장** (삼성 전자칠판/PowerPoint) |
| `토큰_절약_발표.pdf` | 동일 내용 PDF 29쪽 (전자칠판 백업용) |
| `발표_스크립트.md` | 30분 발표 대본 + 시간배분·컷 순서·준비물 |
| `build/` | 덱 빌드 도구 (build_deck · check_layout · make_pdf) |
| `검증보고서.md` | 전수 검증 기록 — 발견한 오류 20건과 조치 |

## 브랜치 구조

이 저장소는 두 브랜치로 나뉩니다.

| 브랜치 | 내용 |
|---|---|
| `main` | 재현 코드 · 실측 원자료 · 페르소나 데모 |
| `presentation` | 덱 · PDF · 발표 대본 · 검증 보고서 · 빌드 도구 ← **현재** |

원칙: **`main`은 저장소 밖을 참조하지 않는다.** 덱이 없어도
`run_all.py`, `demo/compare_personas.py`, `tools/verify_deck.py`가
전부 동작합니다(덱 검사만 SKIP).

## PDF 재생성 (덱을 수정했다면 반드시)

```bash
cd build && python make_pdf.py --check   # 폰트 치환 → 변환 → 검증까지
```

`맑은 고딕`은 Windows 전용이라 Linux/macOS에서 변환하면 폰트가 치환된다.
이 스크립트가 NanumGothic 등으로 자동 매핑하고, 변환 후 쪽수(28)와
한글 텍스트 추출까지 확인해 준다. LibreOffice 필요:
`sudo apt-get install -y libreoffice-impress fonts-nanum`

## 페르소나 비교 데모 (demo/)

같은 메모장을 만드는 두 사람 — 토큰 절약 원칙을 **하나도 안 지킨 A**와
**전부 지킨 B**. 최종 산출물은 글자까지 동일하다.

```bash
git checkout main
python demo/compare_personas.py                 # 입력·출력·사고·캐싱 4축 비교
python demo/compare_personas.py --model opus    # 모델 바꿔도 19~21× 유지
```

| 파일 | 내용 |
|---|---|
| `demo/memo.html` (main) | 바이브 코딩 산출물 — 브라우저로 바로 열림 |
| `demo/비교.html` (main) | 비교 결과 시각화 (발표용) |
| `demo/transcripts/` (main) | 두 페르소나의 대화 전문 (토큰 계측 원본) |

**결과: 입력 96%↓ · 출력 94%↓ · 사고 95%↓ · 비용 20.8× 차이 (연 $20,832 / 10인 팀)**

## 수치 회귀 검사

```bash
python ../tools/verify_deck.py     # 98개 검사, 실패 시 exit 1
```

슬라이드에 박힌 숫자를 **원자료 JSONL에서 다시 계산해 대조**한다.
표 행 합계, 슬라이드 간 기준선 일관성, 정답률, 단가 민감도, 참조 파일 존재까지 본다.
덱이나 원자료를 고쳤다면 이걸 먼저 돌릴 것.

## 재현

```bash
git checkout main
pip install -r requirements.txt
python run_all.py                        # exp01~09 (실호출 없음, 무료)

export GEMINI_API_KEY=...                # 아래부터는 실호출 (과금)
python tools/live_lang_bench.py --n 20 --thinking -1 \
       --out results/live_lang_thinking.jsonl      # 한·영 벤치 N=80
python tools/stats_test.py results/live_lang_thinking.jsonl   # 통계 검정
python tools/thinking_sweep.py --n 6                          # 사고 예산 240배
```

원자료와 검정 출력은 `token-cost-lab/results/`에 이미 들어 있습니다.
(`live_lang_thinking.jsonl` 80행 · `thinking_sweep.jsonl` 30행 ·
`stats_thinking.txt` · `sweep_summary.txt`)

> ⚠️ **슬라이드 6의 N=100 원자료(`live_lang.jsonl`)는 이 패키지에 없습니다.** 해당 수치를
> 검증하려면 `tools/live_lang_bench.py --n 25`를 다시 돌려야 합니다(실호출·과금).

## 핵심 수치

- **한국어는 같은 분량에 1.4~3.0배 비싸다** — 실호출 N=80, 분량 정규화 기준.
  설명형 3.03× (95% CI 2.68–3.47), 추론형 1.36× (95% CI 1.23–1.51), 둘 다 p<0.001.
- **같은 정답률, 240배 요금** — 사고 예산만 바꾼 30회 실측. 사고 끔과 자동 모두 정답률 6/6.
  사고가 켜진 구간에서 과금 출력 토큰의 **99%가 보이지 않는 사고 토큰**.
  (240배는 `gemini-25` 단가 환산값 — flash-lite 공식 단가로는 약 149배)
- 출력 토큰은 입력의 **2~8배** (모델별 단가표 기준).
- 캐싱 −62% · 장황함 제거 −83% · SDD −71% · 리워크 6사이클 16.6배.

## ⚠️ 읽기 전 주의 (오독 방지)

1. **호출당 비용만 비교하면 결론이 뒤집힌다.** 추론형에서는 한국어가 27% *싸* 보이는데,
   한국어가 답을 절반만 썼기 때문이다. **반드시 분량으로 정규화할 것** (`LIVE_RESULTS.md` §6·§7).
2. **실제 과금 입력 = `promptTokenCount` − `cachedContentTokenCount`.**
   차감하지 않으면 캐싱을 잘 걸어놓고도 절감이 리포트에 안 잡힌다.
3. **`thinkingBudget`은 반드시 명시할 것.** 기본값은 모델마다 다르다.
   어중간한 예산(512)은 정답률이 **6회 중 2회**로 떨어졌다 — 충분히 주거나 아예 끌 것.
4. `gemini-2.5-*` 계열은 신규 API 키에서 404다. 실측 모델은 `gemini-3.1-flash-lite`.
5. 스트리밍의 `usageMetadata`는 **청크마다 누적값**이다. 합산하지 말고 마지막 값만 쓸 것.
6. SDD는 **조건부로만 참**이다 (`LIVE_RESULTS.md` 및 슬라이드 19의 반증 참조).

## 전자칠판 준비물

- pptx를 USB로 옮겨 삼성 Flip에서 직접 열거나, PDF를 백업으로 함께 지참.
- 폰트는 **맑은 고딕** 기준. 없으면 PDF로 진행할 것.
- 라이브 시연(슬라이드 25)은 선택. 네트워크 불안 시 슬라이드 표만으로도 논지가 완결된다.
