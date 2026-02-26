# VCMS i18n — 번역 자동화 파이프라인

> VENDIT VCMS 채널 매니저 다국어 번역 관리 저장소

## 📊 현황

| 항목 | 수치 |
|------|------|
| 총 키 수 | 2,677 |
| 지원 언어 | KO, EN, JA, ZH, ES |
| 미번역 키 | **0** (164키 번역 완료) |
| 용어집 | 32개 용어 × 5개 언어 |

## 📁 구조

```
vcms-i18n/
├── locales/           # 번역 파일
│   ├── ko.json        # 한국어 (기준 언어)
│   ├── en.json        # 영어
│   ├── ja.json        # 일본어
│   ├── zh.json        # 중국어 (간체)
│   └── es.json        # 스페인어
├── glossary.json      # 용어집 (32 terms × 5 langs)
├── scripts/
│   └── qa_check.py    # QA 자동 검증 스크립트
├── docs/
│   └── pipeline-design.md  # 파이프라인 설계서
└── README.md
```

## 🔍 QA 검증

```bash
python scripts/qa_check.py --verbose
```

## 📝 2026-02-26 초기 작업 완료

- [x] 164키 미번역 → 4개 언어 번역 완료 (EN 피벗 방식)
- [x] 용어집 32개 용어 정의
- [x] QA 자동 검증 스크립트 작성
- [x] 파이프라인 설계서 작성
