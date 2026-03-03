#!/usr/bin/env python3
"""VCMS i18n Translation Sync: ko -> en,ja,zh,es via Gemini Flash"""
import json, os, sys, re, unicodedata, time, urllib.request, urllib.error

LOCALES_DIR = os.environ.get("LOCALES_DIR", "locales/latest")
GLOSSARY_PATH = os.environ.get("GLOSSARY_PATH", "glossary/glossary.json")
PROMPT_PATH = os.environ.get("PROMPT_PATH", "prompts/translate.txt")
SOURCE_LANG = "ko"
TARGET_LANGS = ["en", "ja", "zh", "es"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
LANG_NAMES = {"en": "English", "ja": "Japanese", "zh": "Simplified Chinese", "es": "Spanish"}

def strip_zw(s):
    return ''.join(c for c in s if unicodedata.category(c) not in ('Cf', 'Mn', 'Cc'))

def load_json(p):
    with open(p, 'r', encoding='utf-8') as f: return json.load(f)

def save_json(p, d):
    with open(p, 'w', encoding='utf-8') as f: json.dump(d, f, ensure_ascii=False, indent=2); f.write('\n')

def load_glossary():
    if not os.path.exists(GLOSSARY_PATH): return []
    return load_json(GLOSSARY_PATH).get("terms", [])

def load_prompt_template():
    if os.path.exists(PROMPT_PATH):
        with open(PROMPT_PATH, 'r', encoding='utf-8') as f: return f.read()
    return "Translate Korean to {lang_name} ({lang_code}).\n{glossary}\nReturn ONLY JSON.\n{source_json}"

def get_path(lang): return os.path.join(LOCALES_DIR, f"{lang}.json")

def cleanup_zw(data):
    cm = {}
    for k, v in data.items():
        ck = strip_zw(k)
        if ck not in cm or len(k) < len(cm[ck][0]): cm[ck] = (k, v)
    r = {}; seen = set()
    for k in data:
        ck = strip_zw(k)
        if ck not in seen: seen.add(ck); r[ck] = cm[ck][1]
    return r, len(data) - len(r)

def build_glossary_text(glossary, tgt):
    if not glossary: return ""
    lk = "zh" if tgt.startswith("zh") else tgt
    lines = []
    for t in glossary:
        val = t.get(lk) or t.get(tgt, "")
        if val:
            note = f" ({t['note']})" if t.get('note') else ""
            lines.append(f"  '{t['ko']}' -> '{val}'{note}")
    return "\n".join(lines)

def call_gemini(prompt):
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192}}).encode('utf-8')
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    for attempt in range(3):
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp: return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 30 * (attempt + 1); print(f"    Rate limited, waiting {wait}s..."); time.sleep(wait)
            else: raise
    return None

def parse_json_response(rd):
    txt = rd["candidates"][0]["content"]["parts"][0]["text"].strip()
    if txt.startswith("```"): txt = re.sub(r'^```\w*\n?', '', txt); txt = re.sub(r'\n?```$', '', txt)
    return json.loads(txt[txt.index("{"):txt.rindex("}")+1])

def translate_batch(texts, tgt, glossary, prompt_tpl):
    if not GEMINI_API_KEY:
        print("  WARN: no GEMINI_API_KEY"); return {k: f"[TODO:{tgt}] {v}" for k, v in texts.items()}
    results = {}; items = list(texts.items()); bs = 30
    for i in range(0, len(items), bs):
        batch = dict(items[i:i+bs])
        prompt = prompt_tpl.replace("{lang_name}", LANG_NAMES.get(tgt, tgt))
        prompt = prompt.replace("{lang_code}", tgt)
        prompt = prompt.replace("{glossary}", build_glossary_text(glossary, tgt))
        prompt = prompt.replace("{source_json}", json.dumps(batch, ensure_ascii=False, indent=2))
        try:
            rd = call_gemini(prompt); parsed = parse_json_response(rd); results.update(parsed)
            um = rd.get("usageMetadata", {})
            print(f"  Batch {i//bs+1}: {len(batch)} keys -> {tgt} (in:{um.get('promptTokenCount',0)} out:{um.get('candidatesTokenCount',0)})")
        except Exception as e:
            print(f"  Batch {i//bs+1} FAILED: {e}")
            for k, v in batch.items(): results[k] = f"[ERROR:{tgt}] {v}"
        if i + bs < len(items): time.sleep(2)
    return results

def main():
    print("=" * 60 + "\nVCMS i18n Translation Sync (Gemini Flash)\n" + "=" * 60)
    glossary = load_glossary(); print(f"Glossary: {len(glossary)} terms")
    prompt_tpl = load_prompt_template(); print(f"Prompt: {PROMPT_PATH}")
    ko_path = get_path(SOURCE_LANG)
    if not os.path.exists(ko_path): print(f"ERROR: {ko_path} not found"); sys.exit(1)
    ko = load_json(ko_path); ko, zw = cleanup_zw(ko); save_json(ko_path, ko)
    print(f"ko.json: {zw} zw-dupes removed, {len(ko)} keys")
    report = {"source_keys": len(ko), "engine": "gemini-2.5-flash", "cost": "$0.00", "languages": {}}
    for lang in TARGET_LANGS:
        print(f"\n--- {lang} ---"); path = get_path(lang)
        if os.path.exists(path): data = load_json(path)
        else: data = {}
        data, zw = cleanup_zw(data)
        if zw: print(f"  {zw} zw-dupes removed")
        missing = [k for k in ko if k not in data]; print(f"  Missing: {len(missing)}")
        tc = 0
        if missing: tr = translate_batch({k: ko[k] for k in missing}, lang, glossary, prompt_tpl); data.update(tr); tc = len(tr)
        for k in [k for k in data if k not in ko]: del data[k]
        ordered = {k: data[k] for k in ko if k in data}; save_json(path, ordered)
        cov = len(ordered) / len(ko) * 100 if ko else 0
        report["languages"][lang] = {"keys": len(ordered), "coverage": f"{cov:.1f}%", "translated": tc}
        print(f"  Saved: {lang}.json ({len(ordered)} keys, {cov:.1f}%)")
    rp = os.path.join(LOCALES_DIR, ".sync-report.json"); save_json(rp, report)
    print(f"\nReport: {rp}")
    for l, i in report["languages"].items(): print(f"  {l}: {i['coverage']} +{i['translated']}")
    print("Done")

if __name__ == "__main__": main()
