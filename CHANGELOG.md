# CHANGELOG — vcms-i18n

## 2026-03-06

- zh-CN → zh 통일: 모든 워크플로우/스크립트에서 zh-CN 제거, zh로 표준화 (i18n-audit.yml, i18n-qa.yml, qa-fix-checked.py, qa_check.py, sync_translations.py)
- zh-TW 번체 지원 추가: 전 파이프라인에 zh-TW 언어 추가 (번역, QA, 감사, Tolgee import/export, 슬랙 알림)
- BLOCK 33 → 0: Gemini Flash로 26키 재번역 (en:12, ja:4, zh:3, zh-TW:3, es:4)
- per-key Tolgee import 안전장치: 200키 초과 차단 + 0.3초 rate limit + 503 backoff 강화 (tolgee-import.yml)
- Tolgee bulk import로 6언어 × 2654키 반영 완료
- GEMINI_API_KEY ~/.env에 추가
