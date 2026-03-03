import json, os, urllib.request
import functions_framework

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

def trigger_workflow(repo, workflow, inputs=None):
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
    body = json.dumps({"ref": "main", "inputs": inputs or {}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 204
    except Exception as e:
        print(f"GitHub failed: {e}")
        return False

def update_msg(url, text):
    body = json.dumps({"replace_original": True, "text": text}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=body,
            headers={"Content-Type": "application/json"}), timeout=10)
    except:
        pass

@functions_framework.http
def handle_slack_callback(request):
    raw = request.form.get("payload", "")
    if not raw:
        return "No payload", 400
    payload = json.loads(raw)
    if payload.get("type") == "block_actions":
        for action in payload.get("actions", []):
            aid = action.get("action_id", "")
            val = json.loads(action.get("value", "{}"))
            user = payload.get("user", {}).get("name", "unknown")
            rurl = payload.get("response_url", "")
            repo = val.get("repo", "yujy118/vcms-i18n")

            if aid == "i18n_translate":
                ok = trigger_workflow(repo, "i18n-auto-sync.yml")
                update_msg(rurl, f"\U0001f504 *{user}* triggered Gemini translation. Running..." if ok else "\u274c Trigger failed.")

            elif aid == "i18n_reject":
                update_msg(rurl, f"\u274c *{user}* rejected.")

    return "", 200
