# VENDIT VCMS i18n 자동화 파이프라인

> VCMS 채널매니저 다국어 번역 자동화. ko 기준 → en / ja / zh / es 자동 번역 + QA + Tolgee 동기화.

## 레포 구조

```
vcms-i18n/
├── .github/workflows/
│   ├── i18n-auto-sync.yml      # 자동 번역 (Gemini Flash)
│   ├── i18n-fix-blocks.yml     # BLOCK 재번역 → PR
│   ├── i18n-audit.yml          # 주간 감사 (매주 월요일)
│   ├── i18n-merge.yml          # 스냅샷 머지
│   ├── il18n-qa.yml            # QA 전용
│   └── tolgee-import.yml       # GitHub → Tolgee 푸시
├── locales/latest/             # 번역 파일 (ko/en/ja/zh/es.json)
├── glossary/glossary.json      # 용어집 (32 terms × 5 langs)
├── prompts/translate.txt       # Gemini 번역 프롬프트
├── scripts/
│   ├── sync_translations.py    # Gemini 번역 엔진 + BLOCK 재번역
│   ├── qa_check.py             # QA 10종 검사
│   ├── notify_slack.py         # Slack 알림 (스레드 상세)
│   └── generate_snapshot.py    # 스냅샷 생성
├── cloud-function/             # Cloud Function (Tolgee 웹훅)
├── snapshots/                  # 번역 스냅샷
└── docs/                       # 설계 문서
```

## 현재 상태

| 항목 | 수치 |
|------|------|
| 총 키 (KO) | 2,656 |
| 번역 커버리지 | EN/JA/ZH/ES 모두 **100%** |
| 용어집 | 32개 term |
| QA 엔진 | 10종 검사 |

## 워크플로우

### 1. i18n Auto Translate (Gemini)

수동 실행. ko.json 기준으로 누락된 키를 Gemini Flash로 번역하고 QA 실행 후 커밋.

```
ko.json 기준 → 누락키 감지 → Gemini 번역 → QA 검사 → 커밋 → Slack 알림
```

### 2. i18n Fix BLOCK (Retranslate → PR)

수동 실행. QA에서 BLOCK으로 잡힌 키만 Gemini로 재번역하고 PR 생성.

```
QA 실행 → BLOCK 키 추출 → Gemini 재번역 → PR 생성 (Before/After 테이블) → Slack 알림
```

- PR body에 전체 수정 내역 (Before/After) 포함
- Slack 메인 메시지 + 스레드에 언어별 상세 목록
- 반드시 PR 리뷰 후 merge

### 3. Tolgee Import

수동 실행. GitHub의 번역 파일을 Tolgee에 푸시.

| 옵션 | 설명 |
|------|------|
| 테스트만 (실제 반영 안 함) | dry_run — 변경 내역만 미리보기 |
| 기존 번역도 덮어쓰기 | force_overwrite — 이미 있는 값도 GitHub 기준으로 갱신 |

### 4. Weekly Audit

매주 월요일 09:00 KST 자동 실행. 전체 QA 스캔 + 용어집 샘플링 + 미번역 키 카운트.

### 5. i18n Merge / QA

스냅샷 머지 및 QA 전용 워크플로우.

## QA 검사 항목 (10종)

| # | 검사 | 심각도 | 설명 |
|---|------|--------|------|
| 1 | 용어집 위반 | BLOCK | glossary.json 용어 미준수 (Package, Booking, Rate 등) |
| 2 | OTA 브랜드 | BLOCK | 브랜드명 직역/한국어 유출 (야놀자→Yanolja 등) |
| 3 | ES 대문자 | WARN | 스페인어 문중 대문자 오류 |
| 4 | 플레이스홀더 | BLOCK | {변수} 누락 또는 추가 |
| 5 | 줄바꿈 | WARN | \n 수 불일치 (차이 2 이상) |
| 6 | 빈 값 | BLOCK | 번역값 비어있음 |
| 7 | AI 유출 | BLOCK | "I cannot translate" 등 프롬프트 잔여 |
| 8 | HTML 태그 | BLOCK | `<bold>`, `<1>` 등 커스텀 태그 불일치 |
| 9 | 미번역 | WARN | ko와 동일 (변수전용/이모지 제외) |
| 10 | ICU 포맷 | BLOCK | select/plural 포맷 깨짐 |

## Slack 알림

### Auto Translate
- **메인 메시지**: 번역 요약 + QA 카테고리별 건수
- **스레드 답글**: 카테고리별 전체 키 목록 (자동 분할)

### Fix BLOCK
- **메인 메시지**: BLOCK 변화 + 언어별 건수 + PR 리뷰 버튼
- **스레드 답글**: 언어별 Before → After 전체 목록

## 용어집 핵심 규칙

| 한국어 | EN | 주의 |
|--------|-----|------|
| 상품 | Package | NOT Product |
| 예약 | Booking | NOT Reservation |
| 요금 | Rate | NOT Price/Fee |
| 숙소 | Property | NOT Accommodation (UI) |
| 판매 완료 | Sold | NOT Sold Out |
| 연동 | Connect | verb form |

전체 32개 용어 → `glossary/glossary.json` 참조.

## Secrets 설정

| Secret | 용도 |
|--------|------|
| `GEMINI_API_KEY` | Gemini Flash 번역 API |
| `SLACK_BOT_TOKEN` | Slack 알림 |
| `SLACK_CHANNEL` | Slack 채널 ID |
| `TOLGEE_API_KEY` | Tolgee API |
| `TOLGEE_URL` | Tolgee 서버 URL |
| `TOLGEE_PROJECT_ID` | Tolgee 프로젝트 ID |

## 대상 언어

| 코드 | 언어 | 파일명 |
|------|------|--------|
| ko | 한국어 (기준) | ko.json |
| en | English | en.json |
| ja | 日本語 | ja.json |
| zh | 中文 | zh.json (GitHub) / zh (Tolgee) |
| es | Español | es.json |
