"""GCP Cloud Function - Slack callback handler for i18n approve/reject"""
import json, os, urllib.request
import functions_framework
from flask import Request

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

def trigger_deploy(repo, run_id):
    url=f"https://api.github.com/repos/{repo}/actions/workflows/i18n-deploy.yml/dispatches"
    body=json.dumps({"ref":"main","inputs":{"source_run_id":str(run_id),"approved_by":"slack"}}).encode()
    req=urllib.request.Request(url,data=body,headers={"Authorization":f"token {GITHUB_TOKEN}","Accept":"application/vnd.github.v3+json","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r: return r.status==204
    except Exception as e: print(f"GitHub failed: {e}"); return False

def update_msg(url, text):
    body=json.dumps({"replace_original":True,"text":text}).encode()
    try: urllib.request.urlopen(urllib.request.Request(url,data=body,headers={"Content-Type":"application/json"}),timeout=10)
    except: pass

@functions_framework.http
def handle_slack_callback(request: Request):
    raw=request.form.get("payload","")
    if not raw: return "No payload",400
    payload=json.loads(raw)
    if payload.get("type")=="block_actions":
        for action in payload.get("actions",[]):
            aid=action.get("action_id","")
            val=json.loads(action.get("value","{}"))
            user=payload.get("user",{}).get("name","unknown")
            rurl=payload.get("response_url","")
            repo=val.get("repo","yujy118/vcms-i18n")
            rid=val.get("run_id","")
            if aid=="i18n_approve":
                ok=trigger_deploy(repo,rid)
                update_msg(rurl, f"\u2705 *{user}* approved. Deploying..." if ok else f"\u274c Deploy trigger failed.")
            elif aid=="i18n_reject":
                update_msg(rurl, f"\u274c *{user}* rejected. Fix and re-push.")
    return "",200
