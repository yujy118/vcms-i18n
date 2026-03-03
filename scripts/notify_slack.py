#!/usr/bin/env python3
"""VCMS i18n Slack Notification with Approve/Reject buttons"""
import json, os, sys, urllib.request, urllib.error

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "C0AF34D4MK5")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "yujy118/vcms-i18n")
GITHUB_RUN_ID = os.environ.get("GITHUB_RUN_ID", "")
REPORT_PATH = os.environ.get("REPORT_PATH", "locales/latest/.sync-report.json")
QA_REPORT_PATH = os.environ.get("QA_REPORT_PATH", "")

def send_slack(blocks):
    if not SLACK_BOT_TOKEN:
        print("No SLACK_BOT_TOKEN"); print(json.dumps(blocks,ensure_ascii=False,indent=2)); return
    body=json.dumps({"channel":SLACK_CHANNEL,"blocks":blocks}).encode('utf-8')
    req=urllib.request.Request("https://slack.com/api/chat.postMessage",data=body,
        headers={"Content-Type":"application/json; charset=utf-8","Authorization":f"Bearer {SLACK_BOT_TOKEN}"})
    try:
        with urllib.request.urlopen(req,timeout=30) as resp:
            r=json.loads(resp.read().decode())
            print("Slack sent" if r.get("ok") else f"Slack error: {r.get('error')}")
    except Exception as e: print(f"Slack failed: {e}")

def main():
    report={}
    if os.path.exists(REPORT_PATH):
        with open(REPORT_PATH) as f: report=json.load(f)
    qa_issues=[]
    if QA_REPORT_PATH and os.path.exists(QA_REPORT_PATH):
        with open(QA_REPORT_PATH) as f: qa_issues=json.load(f)

    src_keys=report.get("source_keys",0)
    langs=report.get("languages",{})
    blk_cnt=len([i for i in qa_issues if i.get("severity")=="BLOCK"])
    wrn_cnt=len([i for i in qa_issues if i.get("severity")=="WARNING"])
    total_tr=sum(v.get("translated",0) for v in langs.values())
    status="\U0001f6a8" if blk_cnt>0 else ("\u26a0\ufe0f" if wrn_cnt>0 else "\u2705")
    run_url=f"https://github.com/{GITHUB_REPOSITORY}/actions/runs/{GITHUB_RUN_ID}"

    lang_lines=[]
    for lang,info in langs.items():
        e="\u2705" if info.get("translated",0)==0 else "\U0001f195"
        lang_lines.append(f"{e} *{lang}*: {info['coverage']} (+{info.get('translated',0)} new)")

    blocks=[
        {"type":"header","text":{"type":"plain_text","text":f"{status} VCMS i18n \ubc88\uc5ed \ub3d9\uae30\ud654 \uc644\ub8cc"}},
        {"type":"section","fields":[
            {"type":"mrkdwn","text":f"*\uc18c\uc2a4 \ud0a4:*\n{src_keys}"},
            {"type":"mrkdwn","text":f"*\uc2e0\uaddc \ubc88\uc5ed:*\n{total_tr}"},
            {"type":"mrkdwn","text":f"*QA BLOCK:*\n{blk_cnt}"},
            {"type":"mrkdwn","text":f"*QA WARNING:*\n{wrn_cnt}"}
        ]},
        {"type":"divider"},
        {"type":"section","text":{"type":"mrkdwn","text":"*\uc5b8\uc5b4\ubcc4 \uc0c1\ud0dc:*\n"+"\n".join(lang_lines)}}
    ]

    if blk_cnt>0:
        bd=[i for i in qa_issues if i.get("severity")=="BLOCK"][:5]
        dt="*\U0001f6a8 BLOCK \uc774\uc288:*\n"
        for issue in bd: dt+=f"\u2022 `[{issue['lang']}]` {issue['check']}: {issue['key']}\n"
        if blk_cnt>5: dt+=f"_...\uc678 {blk_cnt-5}\uac74_"
        blocks.append({"type":"section","text":{"type":"mrkdwn","text":dt}})

    blocks.append({"type":"divider"})
    blocks.append({"type":"actions","block_id":"i18n_approval","elements":[
        {"type":"button","text":{"type":"plain_text","text":"\u2705 \uc2b9\uc778 \u2014 \ubc30\ud3ec"},"style":"primary",
         "action_id":"i18n_approve","value":json.dumps({"run_id":GITHUB_RUN_ID,"repo":GITHUB_REPOSITORY}),
         "confirm":{"title":{"type":"plain_text","text":"\ubc88\uc5ed \ubc30\ud3ec \uc2b9\uc778"},
                     "text":{"type":"mrkdwn","text":f"\ubc88\uc5ed \uacb0\uacfc\ub97c locales/latest/\uc5d0 \ubc18\uc601\ud569\ub2c8\ub2e4.\nBLOCK: {blk_cnt}\uac74"},
                     "confirm":{"type":"plain_text","text":"\uc2b9\uc778"},"deny":{"type":"plain_text","text":"\ucde8\uc18c"}}},
        {"type":"button","text":{"type":"plain_text","text":"\u274c \ubc18\ub824"},"style":"danger",
         "action_id":"i18n_reject","value":json.dumps({"run_id":GITHUB_RUN_ID,"repo":GITHUB_REPOSITORY})},
        {"type":"button","text":{"type":"plain_text","text":"\U0001f4cb \uc0c1\uc138"},"action_id":"i18n_view","url":run_url}
    ]})
    send_slack(blocks)

if __name__=="__main__": main()
