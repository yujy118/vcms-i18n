# VENDIT VCMS 번역 자동화 파이프라인

> **목적:** PM이 승인/샘플링만 하는 구조. 코드 접근 없는 PM이 운영 가능.

## 레포 구조

```
vcms-i18n/
├── locales/           # Tolgee 번역 파일 (KO/EN/JA/ZH/ES)
├── glossary/          # 용어집 (32 terms × 5 langs)
├── analysis/          # 분석 결과 (미번역 키, 배치 분류)
├── scripts/           # QA 및 자동화 스크립트
└── docs/              # 설계 문서
```

## 현재 상태

| 항목 | 수치 |
|------|------|
| 총 키 (KO) | 2,677 |
| 번역 완료 (EN/JA/ZH/ES) | 2,513 |
| **미번역** | **164키** |
| 용어집 | 32개 term |

### 미번역 164키 배치 분류

| 배치 | 키 수 | 리뷰 방식 |
|------|------|-----------|
| Batch 1: Payment | 38키 | PM 전수 리뷰 |
| Batch 2: Subscription | 124키 | PM 전수 리뷰 |
| Batch 3: Other | 2키 | PM 샘플링 |

## 파이프라인 Phase

- **Phase 0 (즉시):** Tolgee Auto-translate ON, 용어집 등록
- **Phase 1 (1주차):** 라벨 자동 태깅, Batch 1 번역
- **Phase 2 (2~3주차):** Batch 2~3 번역, QA 스크립트
- **Phase 3 (4주차):** GitHub Actions 연동
- **Phase 4 (운영):** 자동화 파이프라인 운영
