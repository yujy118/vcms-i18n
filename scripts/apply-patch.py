#!/usr/bin/env python3
"""Apply translation patch to locale files.
Usage: python scripts/apply-patch.py patches/translation-fix-001.json
"""
import json, sys
from pathlib import Path

LOCALES = Path("locales/latest")
LANG_MAP = {"en": "en.json", "ja": "ja.json", "zh": "zh.json", "es": "es.json"}

patch_file = sys.argv[1] if len(sys.argv) > 1 else "patches/translation-fix-001.json"
patch = json.load(open(patch_file, encoding="utf-8"))

for key, langs in patch.items():
    for lang, value in langs.items():
        fname = LANG_MAP.get(lang, f"{lang}.json")
        path = LOCALES / fname
        if not path.exists():
            print(f"  SKIP {fname} (not found)")
            continue
        data = json.load(open(path, encoding="utf-8"))
        old = data.get(key, "")
        data[key] = value
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        status = "CHANGED" if old != value else "SAME"
        print(f"  [{lang}] {key}: {status}")

print("Patch applied.")
