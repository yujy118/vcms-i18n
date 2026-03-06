#!/usr/bin/env python3
"""VCMS i18n Translation Sync: ko -> en,ja,zh,zh-TW,es via Gemini/Anthropic
  --fix-blocks: Retranslate only QA BLOCK keys (for PR review)
  Engine selection: TRANSLATION_ENGINE env var (default: anthropic, fallback: gemini)
"""
import json, os, sys, re, unicodedata, time, urllib.request, urllib.error, argparse

LOCALES_DIR = os.environ.get("LOCALES_DIR", "locales/latest")
GLOSSARY_PATH = os.environ.get("GLOSSARY_PATH", "glossary/glossary.json")
PROMPT_PATH = os.environ.get("PROMPT_PATH", "prompts/translate.txt")
SOURCE_LANG = "ko"
TARGET_LANGS = ["en", "ja", "zh", "zh-TW", "es"]
TRANSLATION_ENGINE = os.environ.get("TRANSLATION_ENGINE", "anthropic").lower()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
LANG_NAMES = {
    "en": "English",
    "ja": "Japanese",
    "zh": "Simplified Chinese",
    "zh-TW": "Traditional Chinese (Taiwan)",
    "es": "Spanish"
}


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
    """언어별 glossary 텍스트 생성.
    정확한 언어 코드 필드 우선 (zh-TW, zh-CN 등 구분).
    fallback: zh-XX -> zh, 그 외 -> tgt
    """
    if not glossary: return ""
    def pick_val(t, lang):
        if lang in t: return t[lang]          # 정확한 매핑 (zh-TW → zh-TW 필드)
        if lang.startswith("zh"): return t.get("zh", "")  # zh-XX fallback → zh
        return t.get(lang, "")
    lines = []
    for t in glossary:
        val = pick_val(t, tgt)
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

def call_anthropic(prompt):
    payload = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 8192,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": prompt}]
    }).encode('utf-8')
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    for attempt in range(3):
        req = urllib.request.Request(ANTHROPIC_URL, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = json.loads(resp.read().decode())
                # Normalize to Gemini-like format for parse_json_response
                text = ""
                for block in raw.get("content", []):
                    if block.get("type") == "text":
                        text += block["text"]
                usage = raw.get("usage", {})
                return {
                    "candidates": [{"content": {"parts": [{"text": text}]}}],
                    "usageMetadata": {
                        "promptTokenCount": usage.get("input_tokens", 0),
                        "candidatesTokenCount": usage.get("output_tokens", 0)
                    }
                }
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 30 * (attempt + 1); print(f"    Rate limited, waiting {wait}s..."); time.sleep(wait)
            else: raise
    return None

def parse_json_response(rd):
    txt = rd["candidates"][0]["content"]["parts"][0]["text"].strip()
    if txt.startswith("```"): txt = re.sub(r'^```\w*\n?', '', txt); txt = re.sub(r'\n?```$', '', txt)
    return json.loads(txt[txt.index("{"):txt.rindex("}")+1])

def _get_engine():
    """Select translation engine. Default: anthropic, fallback: gemini."""
    if TRANSLATION_ENGINE == "anthropic" and ANTHROPIC_API_KEY:
        return "anthropic", call_anthropic
    if TRANSLATION_ENGINE == "gemini" and GEMINI_API_KEY:
        return "gemini", call_gemini
    # Fallback: try anthropic first, then gemini
    if ANTHROPIC_API_KEY:
        return "anthropic", call_anthropic
    if GEMINI_API_KEY:
        return "gemini", call_gemini
    return None, None

def translate_batch(texts, tgt, glossary, prompt_tpl):
    engine_name, engine_fn = _get_engine()
    if engine_fn is None:
        print("  WARN: no API key set (ANTHROPIC_API_KEY or GEMINI_API_KEY)"); return {k: f"[TODO:{tgt}] {v}" for k, v in texts.items()}
    results = {}; items = list(texts.items()); bs = 30
    for i in range(0, len(items), bs):
        batch = dict(items[i:i+bs])
        prompt = prompt_tpl.replace("{lang_name}", LANG_NAMES.get(tgt, tgt))
        prompt = prompt.replace("{lang_code}", tgt)
        prompt = prompt.replace("{glossary}", build_glossary_text(glossary, tgt))
        prompt = prompt.replace("{source_json}", json.dumps(batch, ensure_ascii=False, indent=2))
        try:
            rd = engine_fn(prompt); parsed = parse_json_response(rd); results.update(parsed)
            um = rd.get("usageMetadata", {})
            print(f"  Batch {i//bs+1}: {len(batch)} keys -> {tgt} [{engine_name}] (in:{um.get('promptTokenCount',0)} out:{um.get('candidatesTokenCount',0)})")
        except Exception as e:
            print(f"  Batch {i//bs+1} FAILED: {e}")
            for k, v in batch.items(): results[k] = f"[ERROR:{tgt}] {v}"
        if i + bs < len(items): time.sleep(2)
    return results


# ========== Fix Blocks Mode ==========
def get_block_keys_by_lang(qa_path):
    """Extract BLOCK keys grouped by lang from QA report.
    Returns: {lang: [key1, key2, ...]}
    """
    if not os.path.exists(qa_path):
        print(f"ERROR: QA report not found: {qa_path}")
        return {}
    qa = load_json(qa_path)
    blocks = [i for i in qa if i.get("severity") == "BLOCK"]
    by_lang = {}
    for issue in blocks:
        lang = issue.get("lang", "")
        key = issue.get("key", "")
        if lang and key and lang != "ko":
            if lang not in by_lang:
                by_lang[lang] = set()
            by_lang[lang].add(key)
    # Convert sets to sorted lists
    return {lang: sorted(keys) for lang, keys in by_lang.items()}


def fix_blocks(qa_path):
    """Retranslate only BLOCK keys from QA report."""
    engine_name, _ = _get_engine()
    engine_label = engine_name or "no-engine"
    print("=" * 60)
    print(f"VCMS i18n Fix BLOCK Keys ({engine_label})")
    print("=" * 60)

    glossary = load_glossary()
    print(f"Glossary: {len(glossary)} terms")
    prompt_tpl = load_prompt_template()

    ko_path = get_path(SOURCE_LANG)
    ko = load_json(ko_path)
    print(f"ko.json: {len(ko)} keys")

    block_keys = get_block_keys_by_lang(qa_path)
    if not block_keys:
        print("No BLOCK keys found. Nothing to fix.")
        return {"fixed": 0, "languages": {}}

    total_keys = sum(len(v) for v in block_keys.values())
    print(f"\nBLOCK keys to retranslate: {total_keys}")
    for lang, keys in block_keys.items():
        print(f"  {lang}: {len(keys)} keys")

    report = {"fixed": 0, "languages": {}, "details": {}}

    for lang, keys in block_keys.items():
        print(f"\n--- {lang}: {len(keys)} BLOCK keys ---")
        path = get_path(lang)
        if not os.path.exists(path):
            print(f"  SKIP: {path} not found")
            continue

        data = load_json(path)

        # Build source dict: ko values for block keys
        source = {}
        for k in keys:
            if k in ko:
                source[k] = ko[k]
            else:
                print(f"  SKIP: {k} not in ko.json")

        if not source:
            print("  No keys to translate")
            continue

        # Save before values
        before_vals = {k: data.get(k, "") for k in source}

        # Show before values
        print(f"  Retranslating {len(source)} keys...")
        for k in list(source.keys())[:5]:
            old = data.get(k, "")
            print(f"    {k}: {old[:60]}...")

        # Translate
        translated = translate_batch(source, lang, glossary, prompt_tpl)

        # Apply and track changes
        changed = 0
        lang_details = []
        for k, new_val in translated.items():
            old_val = before_vals.get(k, "")
            if old_val != new_val:
                data[k] = new_val
                changed += 1
                lang_details.append({
                    "key": k,
                    "before": old_val[:200],
                    "after": new_val[:200],
                })

        # Save (preserve key order from ko.json)
        ordered = {k: data[k] for k in ko if k in data}
        save_json(path, ordered)
        print(f"  Changed: {changed}/{len(source)} keys")
        report["languages"][lang] = {"keys": len(source), "changed": changed}
        report["details"][lang] = lang_details
        report["fixed"] += changed

    # Save fix report
    fix_report_path = os.path.join(LOCALES_DIR, ".fix-report.json")
    save_json(fix_report_path, report)
    print(f"\nFix report: {fix_report_path}")
    print(f"Total fixed: {report['fixed']} keys")
    return report


# ========== Normal Sync Mode ==========
def sync():
    engine_name, _ = _get_engine()
    engine_label = engine_name or "no-engine"
    print("=" * 60 + f"\nVCMS i18n Translation Sync ({engine_label})\n" + "=" * 60)
    glossary = load_glossary(); print(f"Glossary: {len(glossary)} terms")
    prompt_tpl = load_prompt_template(); print(f"Prompt: {PROMPT_PATH}")
    ko_path = get_path(SOURCE_LANG)
    if not os.path.exists(ko_path): print(f"ERROR: {ko_path} not found"); sys.exit(1)
    ko = load_json(ko_path); ko, zw = cleanup_zw(ko); save_json(ko_path, ko)
    print(f"ko.json: {zw} zw-dupes removed, {len(ko)} keys")
    report = {"source_keys": len(ko), "engine": engine_label, "cost": "$0.00", "languages": {}}
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


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--fix-blocks", action="store_true", help="Retranslate QA BLOCK keys only")
    p.add_argument("--qa-report", default="locales/latest/.qa-report.json", help="QA report path")
    args = p.parse_args()

    if args.fix_blocks:
        fix_blocks(args.qa_report)
    else:
        sync()
