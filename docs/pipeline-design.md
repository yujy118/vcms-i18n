# VENDIT VCMS 번역 자동화 파이프라인 설계서

> **목적:** "진영님 이거 했어요?" 제거. PM이 승인/샘플링만 하는 구조.
> **원칙:** 코드 접근 없는 PM이 운영 가능. 개발자 요청은 최소화.
> **작성일:** 2026-02-26

*전체 설계서는 프로젝트 대화 내역 참조*

---

## Phase 계획 요약

### Phase 0: 즉시 (PM 혼자, 2시간)
- Tolgee Auto-translate ON
- Chrome Plugin 설치
- 용어집 32개 Tolgee에 등록
- 리뷰 워크플로우 테스트

### Phase 1: 1주차 (PM + Claude, 1~2일)
- ✅ Missing 164키 번역 완료 (이 레포에 반영됨)
- Tolgee API로 기존 키에 라벨 자동 부여 (1,510키)
- 불필요 키 라벨 부여 (215키)
- PM 전수 리뷰 (Batch 1: payment 42키)

### Phase 2: 2~3주차 (3~4일)
- Batch 2 (subscription 34키) 리뷰
- Batch 3 (other 88키) 리뷰
- 기존 132건 불일치 수정
- QA 자동 검증 스크립트 Tolgee 연동

### Phase 3: 4주차 (개발자 반나절)
- GitHub Actions에 tolgee push/pull 연동
- Tolgee Webhook → Slack 알림 연동
- Reviewed 상태만 pull 하도록 설정

### Phase 4: 운영 (지속)
- 실시간: 새 키 → 자동번역 → QA → 리뷰 요청
- 주 1회: 주간 리포트 + 샘플링 리뷰
- 월 1회: 용어집 업데이트, 프로덕션 스팟체크