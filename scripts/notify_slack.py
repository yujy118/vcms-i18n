#!/usr/bin/env python3
"""VCMS i18n Slack - Translation report with threaded QA detail"""
import json, os, urllib.request

TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
CHANNEL = os.environ.get("SLACK_CHANNEL", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "yujy118/vcms-i18n")
RUN_ID = os.environ.get("GITHUB_RUN_ID", "")
REPORT = os.environ.get("REPORT_PATH", "locales/latest/.sync-report.json")
QA_PATH = os.environ.get("QA_REPORT_PATH", "locales/latest/.qa-report.json")


def slack_post(payload):
    if not TOKEN:
        print("No SLACK_BOT_TOKEN")
        return None
    body = json.dumps(payload).encode()
    req = urllib.request.Request("https://slack.com/api/chat.postMessage", data=body,
        headers={"Content-Type": "application/json;charset=utf-8", "Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
            if d.get("ok"):
                print("Slack OK")
                return d.get("ts")  # return thread timestamp
            else:
                print(f"Slack err: {d.get('error')}")
                return None
    except Exception as e:
        print(f"Slack fail: {e}")
        return None


def post_thread(thread_ts, text):
    """Post a reply in thread"""
    return slack_post({
        "channel": CHANNEL,
        "thread_ts": thread_ts,
        "text": text,
        "unfurl_links": False,
    })


def chunk_messages(items, title, formatter, max_chars=2800):
    """Split items into multiple messages if too long"""
    messages = []
    current = f"{title}\n\n"
    for item in items:
        line = formatter(item) + "\n"
        if len(current) + len(line) > max_chars:
            messages.append(current.strip())
            current = f"{title} (계속)\n\n"
        current += line
    if current.strip() and current.strip() != title:
        messages.append(current.strip())
    return messages


def main():
    report = {}
    if os.path.exists(REPORT):
        report = json.load(open(REPORT))
    qa = []
    if os.path.exists(QA_PATH):
        qa = json.load(open(QA_PATH))

    src = report.get("source_keys", 0)
    engine = report.get("engine", "unknown")
    cost = report.get("cost", "N/A")
    langs = report.get("languages", {})
    blk = [i for i in qa if i.get("severity") == "BLOCK"]
    wrn = [i for i in qa if i.get("severity") == "WARNING"]
    total_tr = sum(v.get("translated", 0) for v in langs.values())
    status = "\U0001f6a8" if blk else ("\u26a0\ufe0f" if wrn else "\u2705")
    run_url = f"https://github.com/{REPO}/actions/runs/{RUN_ID}"

    lang_lines = []
    for lang, info in langs.items():
        e = "\u2705" if info.get("translated", 0) == 0 else "\U0001f195"
        lang_lines.append(f"{e} *{lang}*: {info['coverage']} (+{info.get('translated', 0)})")

    # ===== Main message (summary only) =====
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{status} i18n 번역 완료 ({engine})"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*소스:* {src}키"},
            {"type": "mrkdwn", "text": f"*신규:* {total_tr}건"},
            {"type": "mrkdwn", "text": f"*QA:* BLOCK {len(blk)} / WARN {len(wrn)}"},
            {"type": "mrkdwn", "text": f"*비용:* {cost}"},
        ]},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*언어별:*\n" + "\n".join(lang_lines)}},
    ]

    # QA summary in main message
    if blk or wrn:
        blocks.append({"type": "divider"})
        summary = ""
        # Count by check type
        by_check = {}
        for i in qa:
            c = i.get("check", "unknown")
            by_check[c] = by_check.get(c, 0) + 1
        for check, count in sorted(by_check.items(), key=lambda x: -x[1]):
            icon = "\U0001f6a8" if any(i["check"] == check and i["severity"] == "BLOCK" for i in qa) else "\u26a0\ufe0f"
            summary += f"{icon} {check}: {count}건\n"
        summary += "\n_\U0001f447 스레드에서 전체 목록 확인_"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": summary.strip()}})

    blocks.append({"type": "divider"})
    blocks.append({"type": "actions", "elements": [
        {"type": "button", "text": {"type": "plain_text", "text": "\U0001f4cb 상세 로그"}, "url": run_url},
    ]})

    # Post main message
    ts = slack_post({"channel": CHANNEL, "blocks": blocks, "text": f"{status} i18n 번역: +{total_tr} BLOCK:{len(blk)} WARN:{len(wrn)}"})
    if not ts:
        return

    # ===== Thread replies: full detail by category =====
    if not qa:
        return

    # Group issues by check type
    by_type = {}
    for i in qa:
        c = i.get("check", "unknown")
        if c not in by_type:
            by_type[c] = []
        by_type[c].append(i)

    # Category display config
    LABELS = {
        "brand_translated": "\U0001f3f7\ufe0f 브랜드명 직역",
        "brand_not_english": "\U0001f3f7\ufe0f 브랜드명 한국어 유출",
        "glossary_violation": "\U0001f4d6 용어집 위반",
        "es_capitalization": "\U0001f520 ES 대문자",
        "placeholder_missing": "\u274c 플레이스홀더 누락",
        "placeholder_extra": "\u2795 플레이스홀더 추가",
        "newline_mismatch": "\u21a9\ufe0f 줄바꿈 불일치",
        "empty": "\U0001f6ab 빈 값",
        "ai_leak": "\U0001f916 AI 프롬프트 유출",
        "html_broken": "\U0001f3f7\ufe0f HTML 태그 깨짐",
        "untranslated": "\U0001f4ad 미번역",
        "icu_broken": "\u26a0\ufe0f ICU 포맷 깨짐",
        "icu_mismatch": "\u26a0\ufe0f ICU 불일치",
    }

    # Post each category as a thread reply
    for check_type in ["brand_translated", "brand_not_english", "glossary_violation",
                        "placeholder_missing", "html_broken", "icu_broken", "icu_mismatch",
                        "empty", "ai_leak", "es_capitalization", "placeholder_extra",
                        "newline_mismatch", "untranslated"]:
        items = by_type.get(check_type, [])
        if not items:
            continue

        label = LABELS.get(check_type, check_type)
        severity = items[0].get("severity", "")
        title = f"{label} ({len(items)}건) [{severity}]"

        def fmt(i):
            msg = i.get("message", "")
            val = i.get("value", "")
            line = f"\u2022 `[{i['lang']}]` `{i['key']}`"
            if msg:
                line += f"\n   {msg}"
            if val:
                line += f"\n   _{val[:80]}_"
            return line

        msgs = chunk_messages(items, title, fmt)
        for msg in msgs:
            post_thread(ts, msg)

    print(f"Thread replies posted for {len(by_type)} categories")


if __name__ == "__main__":
    main()
