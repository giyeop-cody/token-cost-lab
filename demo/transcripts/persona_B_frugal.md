> **증거 등급: 페르소나 비용 시나리오의 전사/예시 자료.**
> API 원응답·청구 usage가 없고 일부 출력은 축약/확대 가정이다.
> 독립적으로 품질이 동등한 두 실제 정책 세션을 측정한 것으로 인용하지 않는다.

# 페르소나 B — 박절약 (토큰 절약 원칙 전부 적용)

> 8년차 백엔드. 같은 사람, 같은 목표, 같은 결과물.
> 차이는 습관뿐: 스펙 선주입 · 영어 사고 · verbosity low · effort 조절 ·
> 캐시 정렬(동적값 뒤로) · 리워크 대신 1회 확정.

---

## SYSTEM (고정 프리픽스 — 한 글자도 안 바뀜 → 2턴부터 캐시 히트)

```
Senior full-stack engineer. Output code only.

Rules:
- No preamble, no plan narration, no post-hoc explanation, no summary.
- Comments only where intent is non-obvious.
- Implement exactly the spec. No speculative abstraction (YAGNI).
- If spec is ambiguous, ask one line. Do not guess.
- Think in English. Reply in Korean only for prose the user reads.
```

> 동적값(시각·세션ID·요청번호)은 시스템 프롬프트 **맨 앞이 아니라 유저 메시지 맨 뒤**로 보낸다.
> 프리픽스가 고정되므로 캐시가 살아 있다.

---

## 턴 1

**USER**

```
단일 HTML 메모장. 스펙 그대로 구현.

[화면]
- 좌: 메모 목록(제목/1줄 미리보기/시각), 우: 편집기(제목 input + 본문 textarea)
- 하단 바: [+ 새 메모] [삭제] + "저장됨" 토스트
- 헤더: 제목 + 메모 개수

[동작]
- 입력 즉시 저장 → localStorage key "memo.notes.v1"
- 스키마: {id, title, body, at}  // at = epoch ms
- 정렬: at 내림차순. 수정 시 최상단으로.
- 목록 클릭 → 해당 메모 편집기에 로드, 선택 항목 하이라이트
- 삭제 → 다음 항목 자동 선택. 없으면 빈 상태
- 빈 목록: "메모가 없습니다 / 새 메모를 만들어 보세요"
- 제목 없으면 "제목 없음", 본문 없으면 "내용 없음"으로 목록 표시
- 시각: 오늘이면 HH:MM, 아니면 M/D

[제약]
- 바닐라 JS. 빌드 없음. 외부 의존 0. 단일 파일.
- 다크 테마. 배경 #0f1720 / 카드 #18222e / 강조 #35d39a
- 폰트 맑은 고딕 우선
- XSS 방지: 사용자 입력은 textContent로만 주입 (innerHTML 금지)
- 반응형: 640px 이하에서 목록 폭 축소, 미리보기 숨김

[완료조건]
- 새로고침 후 데이터 유지
- 목록 클릭 시 정상 로드
- 콘솔 에러 0

--- 요청 컨텍스트 (동적값은 여기 뒤쪽에) ---
현재 시각: 2026-08-15 14:32:07.412
세션 ID: sess_a3f9e21b-77c4-4e02-b1a9-0f2d6c8e5a13
요청 번호: #1
```

**ASSISTANT**

```
(memo.html 전체 — 약 210줄, 설명 없이 코드만)
```

---

## 턴 2

**USER**

```
확인함. 640px 미디어쿼리에서 목록 폭 110px이 너무 좁다. 140px로.

--- 요청 컨텍스트 ---
현재 시각: 2026-08-15 14:41:55.008
요청 번호: #2
```

**ASSISTANT**

```
@media(max-width:640px){
  #list{width:140px} .item p{display:none}
}
```

> 전체 재출력이 아니라 **변경된 블록만.** 이것만으로 출력 토큰이 94% 줄어든다.

---

## 끝

리워크 없음. 2턴에 완료.

- 스펙에 완료조건을 박아 두었으므로 "저장이 안 된다" / "클릭이 안 된다"는 턴이 발생하지 않음
- YAGNI를 명시했으므로 이벤트 버스·syncService·ThemeContext 같은
  **쓰지도 않을 코드가 생성되지 않음** → 생성 비용도, 이후 턴의 재전송 비용도 0
- 사고는 영어로 → 같은 추론에 토큰 1.4~2배 절감
- verbosity low → 계획 서술·단계별 해설·요약 3종 세트 제거
