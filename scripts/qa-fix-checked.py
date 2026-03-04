#!/usr/bin/env python3
"""Parse PR body for checked items, retranslate them via Claude API, update locale files."""
import json, re, sys, os, time
from pathlib import Path

LOCALES = Path("locales/latest")

def parse_checked_items(pr_body):
    """Extract checked items from PR body markdown checkboxes."""
    checked = []
    pattern = re.compile(r'- \[x\] `([^`]+)` \[([^\]]+)\] (.+?)(?:\n|$)')
    for match in pattern.finditer(pr_body):
        key = match.group(1)
        lang = match.group(2)
        message = match.group(3).split(' — ')[0].strip()
        checked.append({'key': key, 'lang': lang, 'message': message})
    return checked


def load_glossary(path="glossary/glossary.json"):
    """Load glossary for translation context."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    terms = {}
    for t in data.get('terms', []):
        terms[t['ko']] = t
    return terms


def retranslate_batch(items, ko_data, glossary, api_key):
    """Retranslate a batch of items using Claude API."""
    import requests as req

    lang_map = {
        'en': 'English', 'ja': 'Japanese',
        'zh': 'Simplified Chinese', 'zh-CN': 'Simplified Chinese',
        'es': 'Spanish'
    }

    # Group by language
    by_lang = {}
    for item in items:
        lang = item['lang']
        if lang not in by_lang:
            by_lang[lang] = []
        by_lang[lang].append(item)

    results = {}  # {lang: {key: new_value}}

    for lang, lang_items in by_lang.items():
        lang_name = lang_map.get(lang, lang)

        # Build glossary context
        glossary_lines = []
        for term in glossary.values():
            if lang in term:
                glossary_lines.append(f"  {term['ko']} → {term.get(lang, term.get('en', ''))}")
            elif 'en' in term:
                glossary_lines.append(f"  {term['ko']} → {term['en']}")

        # Build keys to translate
        keys_block = []
        for item in lang_items:
            ko_val = ko_data.get(item['key'], '')
            issue = item.get('message', '')
            keys_block.append(f"KEY: {item['key']}\nKO: {ko_val}\nISSUE: {issue}")

        prompt = f"""You are a professional translator for a hotel/accommodation channel manager SaaS (like SiteMinder, Cloudbeds).

Translate the following Korean texts to {lang_name}.

GLOSSARY (MUST follow):
{chr(10).join(glossary_lines[:30])}

RULES:
1. MUST use glossary terms exactly
2. Preserve ALL variables: {{count}}, {{name}}, {{property}}, etc.
3. Preserve ALL HTML tags: <1></1>, <bold></bold>, <primary></primary>, <highlight></highlight>, etc.
4. Preserve ICU format: {{type, select, ...}}
5. Keep \\n line breaks in same positions
6. OTA brand names stay in English: Yanolja, Agoda, Airbnb, etc.

{chr(10).join(keys_block)}

Respond in JSON format only:
{{"translations": {{"KEY_NAME": "translated value", ...}}}}
"""
        try:
            resp = req.post("https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60
            )
            data = resp.json()
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block["text"]

            # Parse JSON from response
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                parsed = json.loads(json_match.group())
                translations = parsed.get("translations", parsed)
                if lang not in results:
                    results[lang] = {}
                results[lang].update(translations)
                print(f"  [{lang}] {len(translations)} keys translated")
        except Exception as e:
            print(f"  [{lang}] API error: {e}")

        time.sleep(1)  # Rate limit

    return results


def apply_fixes(results):
    """Apply retranslated values to locale files."""
    lang_file_map = {
        'en': 'en.json', 'ja': 'ja.json',
        'zh': 'zh.json', 'zh-CN': 'zh.json',
        'es': 'es.json'
    }

    changed_files = []
    for lang, translations in results.items():
        fname = lang_file_map.get(lang, f'{lang}.json')
        path = LOCALES / fname
        if not path.exists():
            print(f"  SKIP {fname}")
            continue

        data = json.load(open(path, encoding='utf-8'))
        changed = 0
        for key, new_val in translations.items():
            if key in data:
                old = data[key]
                if old != new_val:
                    data[key] = new_val
                    changed += 1
                    print(f"  [{lang}] {key}: FIXED")

        if changed > 0:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write('\n')
            changed_files.append(fname)
            print(f"  {fname}: {changed} keys updated")

    return changed_files


if __name__ == '__main__':
    pr_body_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pr-body.md"
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    with open(pr_body_file, encoding='utf-8') as f:
        pr_body = f.read()

    checked = parse_checked_items(pr_body)
    if not checked:
        print("No checked items found")
        sys.exit(0)

    print(f"Found {len(checked)} checked items")

    ko_data = json.load(open(LOCALES / 'ko.json', encoding='utf-8'))
    glossary = load_glossary()

    results = retranslate_batch(checked, ko_data, glossary, api_key)
    changed_files = apply_fixes(results)

    print(f"\nDone: {len(changed_files)} files updated")
