#!/usr/bin/env python3
"""Parse PR body for checked items, retranslate them via Claude API, update locale files."""
import json, re, sys, os, time, argparse
from pathlib import Path

LOCALES = Path("locales/latest")

def parse_checked_items(pr_body, select_all=False):
    """Extract checked (or all) items from PR body markdown checkboxes."""
    checked = []
    if select_all:
        pattern = re.compile(r'- \[[ x]\] `([^`]+)` \[([^\]]+)\] (.+?)(?:\n|$)')
    else:
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

    by_lang = {}
    for item in items:
        lang = item['lang']
        if lang not in by_lang:
            by_lang[lang] = []
        by_lang[lang].append(item)

    results = {}

    for lang, lang_items in by_lang.items():
        lang_name = lang_map.get(lang, lang)

        glossary_lines = []
        for term in glossary.values():
            if lang in term:
                glossary_lines.append(f"  {term['ko']} → {term.get(lang, term.get('en', ''))}")
            elif 'en' in term:
                glossary_lines.append(f"  {term['ko']} → {term['en']}")

        # Batch 15 keys at a time
        for batch_start in range(0, len(lang_items), 15):
            batch = lang_items[batch_start:batch_start+15]
            keys_block = []
            for item in batch:
                ko_val = ko_data.get(item['key'], '')
                issue = item.get('message', '')
                keys_block.append(f"KEY: {item['key']}\nKO: {ko_val}\nISSUE: {issue}")

            prompt = f"""You are a professional translator for a hotel/accommodation channel manager SaaS (like SiteMinder, Cloudbeds).

Retranslate the following Korean texts to {lang_name}. Each key has an ISSUE explaining what was wrong. Fix the issue.

GLOSSARY (MUST follow exactly):
{chr(10).join(glossary_lines[:40])}

CRITICAL RULES:
1. Use glossary terms EXACTLY as specified
2. Preserve ALL variables: {{count}}, {{name}}, {{property}}, {{channelName}}, etc.
3. Preserve ALL HTML/XML tags exactly: <1></1>, <bold></bold>, <primary></primary>, etc.
4. Preserve ICU format: {{type, select, YEARLY {{...}} other {{...}}}}
5. Keep \\n newlines in same positions as Korean source
6. OTA brand names in English only: Yanolja, Yeogiottae, Agoda, Airbnb, Bookingdotcom, etc.

{chr(10).join(keys_block)}

Respond ONLY with JSON (no markdown, no explanation):
{{"translations": {{"KEY_NAME": "translated value", ...}}}}"""

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
                    timeout=90
                )
                data = resp.json()
                text = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        text += block["text"]

                json_match = re.search(r'\{[\s\S]*\}', text)
                if json_match:
                    parsed = json.loads(json_match.group())
                    translations = parsed.get("translations", parsed)
                    if lang not in results:
                        results[lang] = {}
                    results[lang].update(translations)
                    print(f"  [{lang}] batch {batch_start//15+1}: {len(translations)} keys")
            except Exception as e:
                print(f"  [{lang}] API error: {e}")

            time.sleep(1)

    return results


def apply_fixes(results):
    """Apply retranslated values to locale files."""
    lang_file_map = {
        'en': 'en.json', 'ja': 'ja.json',
        'zh': 'zh.json', 'zh-CN': 'zh.json',
        'es': 'es.json'
    }

    changed_files = []
    fix_details = []
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
                    fix_details.append(f"✅ [{lang}] `{key}`")

        if changed > 0:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write('\n')
            changed_files.append(fname)
            print(f"  {fname}: {changed} keys fixed")

    # Write summary for PR comment
    summary_lines = [f"## 🔧 재번역 완료 ({len(fix_details)}건)\n"]
    summary_lines.extend(fix_details)
    if not fix_details:
        summary_lines = ["재번역 대상이 없거나 API 호출 실패"]
    with open("/tmp/fix-summary.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    # Write changed files list (used by workflow to decide commit)
    with open("/tmp/changed-files.txt", "w") as f:
        f.write("\n".join(changed_files))

    return changed_files


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pr_body_file', nargs='?', default='/tmp/pr-body.md')
    parser.add_argument('--all', action='store_true', help='Fix all items regardless of checkbox state')
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        with open("/tmp/fix-summary.txt", "w") as f:
            f.write("❌ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        with open("/tmp/changed-files.txt", "w") as f:
            f.write("")
        sys.exit(1)

    with open(args.pr_body_file, encoding='utf-8') as f:
        pr_body = f.read()

    checked = parse_checked_items(pr_body, select_all=args.all)
    if not checked:
        print("No items to fix")
        with open("/tmp/fix-summary.txt", "w") as f:
            f.write("선택된 항목이 없습니다. 체크박스를 선택한 후 `/fix`를 입력하세요.")
        with open("/tmp/changed-files.txt", "w") as f:
            f.write("")
        sys.exit(0)

    mode = "ALL" if args.all else "CHECKED"
    print(f"Found {len(checked)} items ({mode})")

    ko_data = json.load(open(LOCALES / 'ko.json', encoding='utf-8'))
    glossary = load_glossary()

    results = retranslate_batch(checked, ko_data, glossary, api_key)
    changed_files = apply_fixes(results)

    print(f"\nDone: {len(changed_files)} files updated")
