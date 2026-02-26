# Weekly Snapshots

주간 번역 상태 스냅샷을 저장합니다.

## 구조

```
snapshots/
├── 2026-W08/
│   └── snapshot.json
├── 2026-W09/
│   └── snapshot.json
└── ...
```

## 보관 정책

- **생성:** 매주 1회 (월요일 기준)
- **보관:** 4주간 유지
- **폐기:** 4주 경과 시 삭제

## snapshot.json 구조

| 필드 | 설명 |
|------|------|
| `key_counts` | 언어별 키 수 |
| `missing_keys` | 미번역 키 목록 |
| `empty_translations` | 빈 번역 수 |
| `glossary_violations` | 용어집 위반 건 |
| `es_charlimit_risk` | ES 글자수 초과 리스크 |
| `zero_width_char_keys` | 제로위드스 문자 키 수 |
| `batch_status` | 배치별 번역/리뷰 진행률 |

## 주간 비교

이전 주 대비 변화를 추적합니다:
- 미번역 키 감소 추이
- 용어집 위반 해결 추이
- 배치 진행률
