#!/bin/bash
# =====================================================
set +H  # zsh history expansion 비활성화
# VCMS i18n 로컬 환경 점검 스크립트
# 실행: bash check_local.sh (vcms-i18n 루트에서)
# =====================================================

RED='\033[0;31m'
YEL='\033[1;33m'
GRN='\033[0;32m'
BLU='\033[0;34m'
NC='\033[0m'

OK()  { echo -e "  ${GRN}✅ $1${NC}"; }
FAIL(){ echo -e "  ${RED}❌ $1${NC}"; }
WARN(){ echo -e "  ${YEL}⚠️  $1${NC}"; }
INFO(){ echo -e "  ${BLU}ℹ️  $1${NC}"; }

echo ""
echo "======================================================"
echo " VCMS i18n 로컬 점검"
echo "======================================================"

# -------------------------------------------------------
# 1. 현재 위치 확인
# -------------------------------------------------------
echo ""
echo "[1] 레포 루트 확인"
if [ -f "glossary/glossary.json" ] && [ -d "scripts" ] && [ -d "locales" ]; then
  OK "vcms-i18n 루트에서 실행 중"
else
  FAIL "vcms-i18n 루트에서 실행해야 합니다"
  FAIL "현재 위치: $(pwd)"
  exit 1
fi

# -------------------------------------------------------
# 2. Python 버전
# -------------------------------------------------------
echo ""
echo "[2] Python 버전"
PY=$(python3 --version 2>&1)
if [[ "$PY" == *"3."* ]]; then
  OK "$PY"
else
  FAIL "python3 없음"
fi

# -------------------------------------------------------
# 3. 환경변수 확인
# -------------------------------------------------------
echo ""
echo "[3] 환경변수"

check_env() {
  local VAR=$1
  local REQUIRED=$2
  local VAL="${!VAR}"
  if [ -n "$VAL" ]; then
    PREVIEW="${VAL:0:8}..."
    OK "$VAR = $PREVIEW"
  else
    if [ "$REQUIRED" = "required" ]; then
      FAIL "$VAR 없음 (필수)"
    else
      WARN "$VAR 없음 (선택)"
    fi
  fi
}

check_env "ANTHROPIC_API_KEY" "required"
check_env "GEMINI_API_KEY" "required"
check_env "SLACK_BOT_TOKEN" "required"
check_env "SLACK_CHANNEL" "required"
check_env "TOLGEE_API_KEY" "optional"

# -------------------------------------------------------
# 4. 파일 존재 확인
# -------------------------------------------------------
echo ""
echo "[4] 필수 파일 존재"

check_file() {
  if [ -f "$1" ]; then
    LINES=$(wc -l < "$1")
    OK "$1 (${LINES}줄)"
  else
    FAIL "$1 없음"
  fi
}

check_file "glossary/glossary.json"
check_file "scripts/qa_check.py"
check_file "scripts/sync_translations.py"
check_file "scripts/notify_slack.py"
check_file "scripts/qa-fix-checked.py"
check_file "locales/latest/ko.json"
check_file "locales/latest/en.json"
check_file "locales/latest/ja.json"
check_file "locales/latest/es.json"

if [ -f "locales/latest/zh-CN.json" ]; then
  LINES=$(wc -l < "locales/latest/zh-CN.json")
  OK "locales/latest/zh-CN.json (${LINES}줄)"
elif [ -f "locales/latest/zh.json" ]; then
  LINES=$(wc -l < "locales/latest/zh.json")
  OK "locales/latest/zh.json (${LINES}줄)"
else
  FAIL "locales/latest/zh.json 또는 zh-CN.json 없음"
fi

# -------------------------------------------------------
# 5. JSON 파싱 검증
# -------------------------------------------------------
echo ""
echo "[5] JSON 파싱 검증"

validate_json() {
  if [ -f "$1" ]; then
    python3 -c "import json; json.load(open('$1'))" 2>/dev/null
    if [ $? -eq 0 ]; then
      KEYS=$(python3 -c "import json; print(len(json.load(open('$1'))))" 2>/dev/null)
      OK "$1 → ${KEYS}키"
    else
      FAIL "$1 JSON 파싱 오류"
    fi
  fi
}

validate_json "glossary/glossary.json"
validate_json "locales/latest/ko.json"
validate_json "locales/latest/en.json"
validate_json "locales/latest/ja.json"
validate_json "locales/latest/es.json"
[ -f "locales/latest/zh-CN.json" ] && validate_json "locales/latest/zh-CN.json"
[ -f "locales/latest/zh.json" ] && validate_json "locales/latest/zh.json"

# -------------------------------------------------------
# 6. 키 커버리지 확인
# -------------------------------------------------------
echo ""
echo "[6] 번역 커버리지"

python3 << 'PYEOF'
import json, os

LOCALES = "locales/latest"
ko = json.load(open(f"{LOCALES}/ko.json", encoding="utf-8"))
total = len(ko)

langs = {}
for l in ["en", "ja", "es"]:
    p = f"{LOCALES}/{l}.json"
    if os.path.exists(p):
        langs[l] = json.load(open(p, encoding="utf-8"))

for fname in ["zh-CN.json", "zh.json"]:
    p = f"{LOCALES}/{fname}"
    if os.path.exists(p):
        langs["zh"] = json.load(open(p, encoding="utf-8"))
        break

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

for lang, data in langs.items():
    missing = [k for k in ko if k not in data]
    extra = [k for k in data if k not in ko]
    pct = (total - len(missing)) / total * 100 if total else 0
    color = GREEN if pct >= 99 else (YELLOW if pct >= 95 else RED)
    icon = "OK" if pct >= 99 else ("WARN" if pct >= 95 else "FAIL")
    print(f"  [{icon}] {lang}: {color}{pct:.1f}%{NC} ({total-len(missing)}/{total}) | 미번역:{len(missing)} 잉여:{len(extra)}")
PYEOF

# -------------------------------------------------------
# 7. QA 실행
# -------------------------------------------------------
echo ""
echo "[7] QA 실행 (qa_check.py)"

python3 scripts/qa_check.py \
  --locales "locales/latest" \
  --glossary glossary/glossary.json \
  --output /tmp/local-qa-report.json 2>&1 | tail -5

if [ -f "/tmp/local-qa-report.json" ]; then
  python3 << 'PYEOF'
import json
qa = json.load(open("/tmp/local-qa-report.json"))
blk = [i for i in qa if i.get("severity") == "BLOCK"]
wrn = [i for i in qa if i.get("severity") == "WARNING"]

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

if not blk:
    print(f"  {GREEN}[OK] BLOCK 없음{NC}")
else:
    print(f"  {RED}[FAIL] BLOCK {len(blk)}건{NC}")
    by_check = {}
    for i in blk:
        c = i.get("check","?")
        by_check[c] = by_check.get(c,0)+1
    for c,n in sorted(by_check.items(), key=lambda x:-x[1]):
        print(f"     - {c}: {n}건")

if not wrn:
    print(f"  {GREEN}[OK] WARNING 없음{NC}")
else:
    print(f"  {YELLOW}[WARN] WARNING {len(wrn)}건{NC}")
PYEOF
fi

# -------------------------------------------------------
# 8. Slack 연결 테스트
# -------------------------------------------------------
echo ""
echo "[8] Slack API 연결 테스트"

if [ -n "$SLACK_BOT_TOKEN" ]; then
  python3 << 'PYEOF'
import urllib.request, json, os
TOKEN = os.environ.get("SLACK_BOT_TOKEN","")
req = urllib.request.Request("https://slack.com/api/auth.test",
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
        if d.get("ok"):
            print(f"  \033[0;32m[OK] Slack 연결 OK — bot: {d.get('user')} / team: {d.get('team')}\033[0m")
        else:
            print(f"  \033[0;31m[FAIL] Slack 오류: {d.get('error')}\033[0m")
except Exception as e:
    print(f"  \033[0;31m[FAIL] Slack 연결 실패: {e}\033[0m")
PYEOF
else
  WARN "SLACK_BOT_TOKEN 없어서 건너뜀"
fi

# -------------------------------------------------------
# 9. Gemini API 연결 테스트
# -------------------------------------------------------
echo ""
echo "[9] Gemini API 연결 테스트"

if [ -n "$GEMINI_API_KEY" ]; then
  python3 << 'PYEOF'
import urllib.request, json, os
KEY = os.environ.get("GEMINI_API_KEY","")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={KEY}"
payload = json.dumps({"contents":[{"parts":[{"text":"hi"}]}],
    "generationConfig":{"maxOutputTokens":5}}).encode()
req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json"})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
        if "candidates" in d:
            print("  \033[0;32m[OK] Gemini API 연결 OK (gemini-2.5-flash)\033[0m")
        else:
            print(f"  \033[1;33m[WARN] 응답 이상: {str(d)[:100]}\033[0m")
except Exception as e:
    err = str(e)
    if "403" in err or "invalid" in err.lower():
        print(f"  \033[0;31m[FAIL] API 키 오류: {err[:100]}\033[0m")
    elif "404" in err:
        print(f"  \033[0;31m[FAIL] 모델 없음: {err[:100]}\033[0m")
    else:
        print(f"  \033[0;31m[FAIL] 연결 실패: {err[:100]}\033[0m")
PYEOF
else
  WARN "GEMINI_API_KEY 없어서 건너뜀"
fi

# -------------------------------------------------------
# 10. Anthropic API 연결 테스트
# -------------------------------------------------------
echo ""
echo "[10] Anthropic API 연결 테스트"

if [ -n "$ANTHROPIC_API_KEY" ]; then
  python3 << 'PYEOF'
import urllib.request, json, os
KEY = os.environ.get("ANTHROPIC_API_KEY","")
payload = json.dumps({
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 5,
    "messages": [{"role":"user","content":"hi"}]
}).encode()
req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload,
    headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
             "content-type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
        if d.get("content"):
            print("  \033[0;32m[OK] Anthropic API 연결 OK\033[0m")
        else:
            print(f"  \033[1;33m[WARN] 응답 이상: {str(d)[:100]}\033[0m")
except Exception as e:
    print(f"  \033[0;31m[FAIL] 연결 실패: {str(e)[:100]}\033[0m")
PYEOF
else
  WARN "ANTHROPIC_API_KEY 없어서 건너뜀"
fi

# -------------------------------------------------------
# 최종 요약
# -------------------------------------------------------
echo ""
echo "======================================================"
echo " 점검 완료"
echo "======================================================"
echo ""
echo "  문제 발견 시 위 [FAIL]/[WARN] 항목 확인"
echo ""
