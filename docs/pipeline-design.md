# VENDIT VCMS 번역 자동화 파이프라인 설계서

> **목적:** "진영님 이거 했어요?" 제거. PM이 승인/샘플링만 하는 구조.
> **원칙:** 코드 접근 없는 PM이 운영 가능. 개발자 요청은 최소화.
> **작성일:** 2026-02-26

---

## 1. 현재 상태 (AS-IS)

```
개발자가 키 추가 → 수동으로 번역 요청 → PM이 추적 → 누락 발생
                                                    ↓
                              용어 불일치, AI 오역, 글자수 초과
```

**수치:**
- 총 2,677키 (KO) / 2,513키 (EN/JA/ZH/ES)
- 164키 미번역 (결제/구독 블록)
- 3건 용어집 위반 확인
- ES 1,875키가 KO의 2배 초과 (UI 깨짐 리스크)
- 38개 제로위드스 문자 키 (레거시)

---

## 2. 목표 상태 (TO-BE)

```
개발자가 키 추가 → [자동] 용어집 기반 번역 → [자동] QA 체크
                                                    ↓
                              PM에게 리뷰 요청 (Slack)
                                                    ↓
                              PM이 샘플링 승인 or 수정 지시
                                                    ↓
                              [자동] Tolgee 반영 → 배포
```

---

## 3. AI 번역 프롬프트 구조

```
1. ROLE
   "You are a professional translator for a Korean hospitality
    technology platform (channel manager for hotels/motels)."

2. GLOSSARY (강제)
   "You MUST use these exact terms. Never deviate:"
   채널 상품 → Channel Package (NOT Channel Product)
   상품 → Package
   대실 → Day-use
   ... (32개 전체 주입)

3. CONTEXT
   "This key is used in: {component_type}"
   "The key name is: {key_name}"

4. CONSTRAINTS
   "Maximum character length: {char_limit}"

5. STYLE
   "Use Title Case for buttons and navigation items."
   "Use sentence case for descriptions and tooltips."

6. OUTPUT FORMAT
   "Return ONLY the translated text. No explanations."
```

---

## 4. 번역 방식: EN 피벗

```
KO → EN → JA/ZH/ES  (권장)

이유:
1. 용어집이 EN 기준으로 확정 → EN이 품질 앵커
2. KO→JA 직접 번역 시 AI가 맥락을 잘못 잡는 경우 많음
3. 숙박 도메인은 글로벌 OTA 용어가 EN 기반

단, JA/ZH는 문화권 차이가 크므로:
  - JA: KO 원문도 함께 참조 (한자어 공유)
  - ZH: 간체자 확인 필수
  - ES: EN 기준이 가장 자연스러움
```

---

## 5. QA 자동 검증 항목

| # | 체크 | 방법 | 심각도 |
|---|------|------|--------|
| 1 | 용어집 위반 | 32개 term 정규식 매칭 | BLOCK |
| 2 | 글자수 초과 | 라벨 기반 CharLimit 비교 | WARNING |
| 3 | 플레이스홀더 누락 | {var} 패턴 KO vs 번역 비교 | BLOCK |
| 4 | 줄바꿈 불일치 | \n 개수 비교 | WARNING |
| 5 | 빈 번역 | 빈 문자열 체크 | BLOCK |
| 6 | AI 프롬프트 누출 | 패턴 매칭 | BLOCK |
| 7 | HTML/마크업 깨짐 | 태그 보존 여부 | BLOCK |
| 8 | 대소문자 규칙 | Title Case 필요 키에 소문자 시작 | WARNING |
| 9 | 중복 번역 | 다른 키인데 동일 KO→다른 번역 | INFO |
| 10 | 미번역(KO=EN) | EN 값이 KO와 동일 | WARNING |

---

## 6. 주간 스냅샷 운영

```
매주 월요일:
  1. generate_snapshot.py 실행 → snapshots/YYYY-WNN/ 저장
  2. 이전 주 대비 변화 추적
  3. 4주 이전 스냅샷 자동 폐기
```

### 스냅샷에 포함되는 항목
- 언어별 키 수
- 미번역 키 목록
- 용어집 위반 건
- ES 글자수 초과 리스크
- 배치별 진행률

---

## 7. Phase 계획

### Phase 0: 즉시 (PM 혼자, 2시간)
- Tolgee Auto-translate ON
- 용어집 32개 Tolgee에 등록
- 리뷰 워크플로우 테스트

### Phase 1: 1주차
- Tolgee API로 기존 키에 라벨 자동 부여 (1,510키)
- Missing 164키 Batch 1 (payment 38키) 번역
- PM 전수 리뷰

### Phase 2: 2~3주차
- Batch 2 (subscription 124키) 번역
- Batch 3 (other 2키) 번역
- QA 자동 검증 스크립트 배포

### Phase 3: 4주차 (개발자 반나절)
- GitHub Actions에 tolgee push/pull 연동
- Reviewed 상태만 pull 하도록 설정

### Phase 4: 운영
- 실시간: 새 키 → 자동번역 → QA → 리뷰
- 주 1회: 주간 스냅샷 + 샘플링 리뷰
- 월 1회: 용어집 업데이트
- 분기 1회: 레거시 키 정리

---

## 8. 성공 지표 (KPI)

| 지표 | 현재 | 3개월 목표 |
|------|------|----------|
| 미번역 키 비율 | 6.1% (164/2677) | 0% |
| 용어집 준수율 | ~99% (위반 3건) | 100% |
| 새 키 번역 리드타임 | 수일~수주 | 24시간 이내 |
| PM 수동 개입 비율 | 100% | 20% |
| ES 글자수 초과 | 1,875건 | < 100 |
