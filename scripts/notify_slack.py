#!/usr/bin/env python3
"""VCMS i18n Slack - Translation completion report with grouped QA issues"""
import json, os, urllib.request

TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
CHANNEL = os.environ.get("SLACK_CHANNEL", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "yujy118/vcms-i18n")
RUN_ID = os.environ.get("GITHUB_RUN_ID", "")
REPORT = os.environ.get("REPORT_PATH", "locales/latest/.sync-report.json")
QA_PATH = os.environ.get("QA_REPORT_PATH", "locales/latest/.qa-report.json")

def post(blocks, text="i18n"):
    if not TOKEN: print("No SLACK_BOT_TOKEN"); return
    body = json.dumps({"channel": CHANNEL, "blocks": blocks, "text": text}).encode()
    req = urllib.request.Request("https://slack.com/api/chat.postMessage", data=body,
        headers={"Content-Type":"application/json;charset=utf-8","Authorization":f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
            print("Slack OK" if d.get("ok") else f"Slack err: {d.get('error')}")
    except Exception as e:
        print(f"Slack fail: {e}")

def main():
    report = {}
    if os.path.exists(REPORT): report = json.load(open(REPORT))
    qa = []
    if os.path.exists(QA_PATH): qa = json.load(open(QA_PATH))

    src = report.get("source_keys", 0)
    engine = report.get("engine", "unknown")
    cost = report.get("cost", "N/A")
    langs = report.get("languages", {})
    blk = len([i for i in qa if i.get("severity") == "BLOCK"])
    wrn = len([i for i in qa if i.get("severity") == "WARNING"])
    total_tr = sum(v.get("translated", 0) for v in langs.values())
    status = "\U0001f6a8" if blk > 0 else ("\u26a0\ufe0f" if wrn > 0 else "\u2705")
    run_url = f"https://github.com/{REPO}/actions/runs/{RUN_ID}"

    lang_lines = []
    for lang, info in langs.items():
        e = "\u2705" if info.get("translated", 0) == 0 else "\U0001f195"
        lang_lines.append(f"{e} *{lang}*: {info['coverage']} (+{info.get('translated',0)})")

    blocks = [
        {"type":"header","text":{"type":"plain_text","text":f"{status} i18n \ubc88\uc5ed \uc644\ub8cc ({engine})"}},
        {"type":"section","fields":[
            {"type":"mrkdwn","text":f"*\uc18c\uc2a4:* {src}\ud0a4"},
            {"type":"mrkdwn","text":f"*\uc2e0\uaddc:* {total_tr}\uac74"},
            {"type":"mrkdwn","text":f"*QA:* BLOCK {blk} / WARN {wrn}"},
            {"type":"mrkdwn","text":f"*\ube44\uc6a9:* {cost}"},
        ]},
        {"type":"divider"},
        {"type":"section","text":{"type":"mrkdwn","text":"*\uc5b8\uc5b4\ubcc4:*\n"+"\n".join(lang_lines)}},
    ]

    # Grouped QA issues
    if blk > 0 or wrn > 0:
        blocks.append({"type":"divider"})
        detail = ""

        brand = [i for i in qa if i.get("check") == "brand_translated"]
        if brand:
            detail += "\U0001f3f7\ufe0f *\ube0c\ub79c\ub4dc\uba85 \uc9c1\uc5ed:*\n"
            for i in brand[:5]:
                detail += f"\u2022 `[{i['lang']}]` {i['key']}: {i['message']}\n"
            if len(brand) > 5: detail += f"_...\uc678 {len(brand)-5}\uac74_\n"
            detail += "\n"

        glos = [i for i in qa if i.get("check") == "glossary_violation"]
        if glos:
            detail += "\U0001f4d6 *\uc6a9\uc5b4\uc9d1 \uc704\ubc18:*\n"
            for i in glos[:5]:
                detail += f"\u2022 `[{i['lang']}]` {i['key']}: {i['message']}\n"
            if len(glos) > 5: detail += f"_...\uc678 {len(glos)-5}\uac74_\n"
            detail += "\n"

        escap = [i for i in qa if i.get("check") == "es_capitalization"]
        if escap:
            detail += "\U0001f520 *ES \ub300\ubb38\uc790:*\n"
            for i in escap[:3]:
                detail += f"\u2022 {i['key']}: {i['message']}\n"
            if len(escap) > 3: detail += f"_...\uc678 {len(escap)-3}\uac74_\n"
            detail += "\n"

        other_b = [i for i in qa if i['severity']=='BLOCK' and i['check'] not in ('brand_translated','glossary_violation')]
        if other_b:
            detail += f"\U0001f6a8 *\uae30\ud0c0 BLOCK:* {len(other_b)}\uac74\n"
            for i in other_b[:3]:
                detail += f"\u2022 `[{i['lang']}]` {i['check']}: {i['key']}\n"
            detail += "\n"

        other_w = [i for i in qa if i['severity']=='WARNING' and i['check'] not in ('es_capitalization',)]
        if other_w:
            detail += f"\u26a0\ufe0f *\uae30\ud0c0 WARNING:* {len(other_w)}\uac74\n"

        if detail:
            blocks.append({"type":"section","text":{"type":"mrkdwn","text":detail.strip()}})

    blocks.append({"type":"divider"})
    blocks.append({"type":"actions","elements":[
        {"type":"button","text":{"type":"plain_text","text":"\U0001f4cb \uc0c1\uc138 \ub85c\uadf8"},"url":run_url},
    ]})

    post(blocks, f"{status} i18n \ubc88\uc5ed: +{total_tr} BLOCK:{blk} WARN:{wrn}")

if __name__ == "__main__":
    main()
