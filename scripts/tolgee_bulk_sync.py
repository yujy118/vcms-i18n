#!/usr/bin/env python3
"""Tolgee Bulk Sync: compare local locale files with Tolgee and push missing translations.

Workflow:
  1. Load local locales from locales/latest/{lang}.json
  2. Fetch all translations from Tolgee (paginated, namespace=vcms)
  3. Find keys that are missing in Tolgee or have UNTRANSLATED/empty translations
  4. Create new keys via import-resolvable API
  5. Fill missing translations via per-key translations API
  6. Print summary

Usage:
  source ~/.env && python3 scripts/tolgee_bulk_sync.py
  source ~/.env && python3 scripts/tolgee_bulk_sync.py --dry-run
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TOLGEE_API_KEY = os.environ.get("TOLGEE_API_KEY", "")
TOLGEE_URL = os.environ.get("TOLGEE_URL", "https://tolgee.internal.vendit.tech")
TOLGEE_PROJECT_ID = os.environ.get("TOLGEE_PROJECT_ID", "4")
NAMESPACE = "vcms"
LANGS = ["ko", "en", "ja", "zh", "zh-TW", "es"]
LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales", "latest")

# ---------------------------------------------------------------------------
# HTTP helpers (urllib only)
# ---------------------------------------------------------------------------

def api_request(method, path, body=None, params=None):
    """Make authenticated request to Tolgee API. Returns parsed JSON."""
    url = f"{TOLGEE_URL.rstrip('/')}/v2/projects/{TOLGEE_PROJECT_ID}{path}"
    if params:
        qs = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
        url += f"?{qs}"

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-API-Key", TOLGEE_API_KEY)
    req.add_header("Content-Type", "application/json")

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            if e.code == 429 or e.code >= 500:
                wait = 2 ** attempt
                print(f"  [retry] HTTP {e.code}, waiting {wait}s... ({path})")
                time.sleep(wait)
                continue
            print(f"  [error] HTTP {e.code}: {err_body[:300]}", file=sys.stderr)
            raise
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"Failed after 3 retries: {method} {path}")


# ---------------------------------------------------------------------------
# Load local locale files
# ---------------------------------------------------------------------------

def load_local_translations():
    """Returns dict: {key_name: {lang: text, ...}, ...}"""
    all_keys = {}
    for lang in LANGS:
        fp = os.path.join(LOCALES_DIR, f"{lang}.json")
        if not os.path.exists(fp):
            print(f"  [warn] Missing locale file: {fp}")
            continue
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, value in data.items():
            if key not in all_keys:
                all_keys[key] = {}
            if value and isinstance(value, str) and value.strip():
                all_keys[key][lang] = value
    return all_keys


# ---------------------------------------------------------------------------
# Fetch all translations from Tolgee (paginated)
# ---------------------------------------------------------------------------

def fetch_tolgee_translations():
    """Returns dict: {key_name: {lang: {"text": str, "state": str}, ...}, ...}"""
    result = {}
    page = 0
    page_size = 250

    while True:
        params = {
            "size": page_size,
            "page": page,
            "filterNamespace": NAMESPACE,
        }
        # Add language query params
        for lang in LANGS:
            params[f"languages"] = lang  # Tolgee uses repeated params; we'll build manually

        # Build URL with repeated language params manually
        base_path = "/translations"
        lang_qs = "&".join(f"languages={urllib.request.quote(l)}" for l in LANGS)
        url = (
            f"{TOLGEE_URL.rstrip('/')}/v2/projects/{TOLGEE_PROJECT_ID}{base_path}"
            f"?size={page_size}&page={page}&filterNamespace={NAMESPACE}&{lang_qs}"
        )

        req = urllib.request.Request(url, method="GET")
        req.add_header("X-API-Key", TOLGEE_API_KEY)
        req.add_header("Content-Type", "application/json")

        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except urllib.error.URLError:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise
        else:
            raise RuntimeError(f"Failed to fetch page {page}")

        embedded = data.get("_embedded", {})
        keys = embedded.get("keys", [])

        if not keys:
            break

        for entry in keys:
            key_name = entry.get("keyName", "")
            translations = entry.get("translations", {})
            result[key_name] = {}
            for lang, t_info in translations.items():
                result[key_name][lang] = {
                    "text": t_info.get("text", ""),
                    "state": t_info.get("state", "UNTRANSLATED"),
                }

        page_info = data.get("page", {})
        total_pages = page_info.get("totalPages", 1)
        print(f"  Fetched page {page + 1}/{total_pages} ({len(keys)} keys)")

        page += 1
        if page >= total_pages:
            break

    return result


# ---------------------------------------------------------------------------
# Diff: figure out what needs to be synced
# ---------------------------------------------------------------------------

def compute_diff(local, tolgee):
    """Returns (new_keys, fill_translations).

    new_keys: list of {keyName, namespace, translations: {lang: {text, ...}}}
        -> keys that don't exist in Tolgee at all
    fill_translations: list of {keyName, lang, text}
        -> keys that exist in Tolgee but have UNTRANSLATED/empty for some languages
    """
    new_keys = []
    fill_translations = []

    for key_name, local_langs in local.items():
        if key_name not in tolgee:
            # Key doesn't exist in Tolgee -> create it
            translations = {}
            for lang, text in local_langs.items():
                translations[lang] = {"text": text, "resolution": "OVERRIDE"}
            new_keys.append({
                "name": key_name,
                "namespace": NAMESPACE,
                "translations": translations,
            })
        else:
            # Key exists in Tolgee -> check each language
            tolgee_langs = tolgee[key_name]
            for lang, text in local_langs.items():
                t_info = tolgee_langs.get(lang, {})
                t_text = t_info.get("text", "")
                t_state = t_info.get("state", "UNTRANSLATED")
                if not t_text or t_state == "UNTRANSLATED":
                    fill_translations.append({
                        "keyName": key_name,
                        "lang": lang,
                        "text": text,
                    })

    return new_keys, fill_translations


# ---------------------------------------------------------------------------
# Push new keys via import-resolvable
# ---------------------------------------------------------------------------

def push_new_keys(new_keys, dry_run=False):
    """Create new keys in Tolgee using import-resolvable endpoint (batched)."""
    if not new_keys:
        return 0

    batch_size = 50
    total = len(new_keys)
    created = 0

    for i in range(0, total, batch_size):
        batch = new_keys[i:i + batch_size]
        if dry_run:
            print(f"  [dry-run] Would create keys {i + 1}-{min(i + len(batch), total)}/{total}")
            created += len(batch)
            continue

        payload = {"keys": batch}
        try:
            api_request("POST", "/keys/import-resolvable", body=payload)
            created += len(batch)
            print(f"  Created keys {i + 1}-{min(i + len(batch), total)}/{total}")
        except Exception as e:
            print(f"  [error] Failed batch {i + 1}-{min(i + len(batch), total)}: {e}", file=sys.stderr)

        if not dry_run and i + batch_size < total:
            time.sleep(0.3)

    return created


# ---------------------------------------------------------------------------
# Fill missing translations (per-key POST)
# ---------------------------------------------------------------------------

def fill_translations(fills, dry_run=False):
    """Fill UNTRANSLATED entries using per-key translations API."""
    if not fills:
        return 0

    total = len(fills)
    filled = 0
    errors = 0

    for idx, item in enumerate(fills):
        key_name = item["keyName"]
        lang = item["lang"]
        text = item["text"]

        if dry_run:
            if idx < 5 or idx == total - 1:
                print(f"  [dry-run] Would fill [{lang}] {key_name[:60]}")
            elif idx == 5:
                print(f"  [dry-run] ... and {total - 5 - 1} more ...")
            filled += 1
            continue

        payload = {
            "key": key_name,
            "namespace": NAMESPACE,
            "translations": {lang: text},
        }

        try:
            api_request("POST", "/translations", body=payload)
            filled += 1
            if (idx + 1) % 50 == 0 or idx == total - 1:
                print(f"  Filled {idx + 1}/{total} translations")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  [error] Fill failed [{lang}] {key_name[:50]}: {e}", file=sys.stderr)

        # Rate limiting: small delay every 10 calls
        if (idx + 1) % 10 == 0:
            time.sleep(0.2)

    if errors > 5:
        print(f"  [error] ... and {errors - 5} more errors", file=sys.stderr)

    return filled


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Tolgee Bulk Sync: push local translations to Tolgee")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()

    if not TOLGEE_API_KEY:
        print("[error] TOLGEE_API_KEY not set. Run: source ~/.env", file=sys.stderr)
        sys.exit(1)

    mode = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{mode}Tolgee Bulk Sync")
    print(f"  URL: {TOLGEE_URL}")
    print(f"  Project: {TOLGEE_PROJECT_ID}")
    print(f"  Namespace: {NAMESPACE}")
    print(f"  Languages: {', '.join(LANGS)}")
    print(f"  Locales dir: {LOCALES_DIR}")
    print()

    # Step 1: Load local translations
    print("[1/5] Loading local locale files...")
    local = load_local_translations()
    local_key_count = len(local)
    local_total = sum(len(v) for v in local.values())
    print(f"  Loaded {local_key_count} keys ({local_total} total translations)")
    print()

    # Step 2: Fetch Tolgee translations
    print("[2/5] Fetching translations from Tolgee...")
    tolgee = fetch_tolgee_translations()
    tolgee_key_count = len(tolgee)
    print(f"  Found {tolgee_key_count} keys in Tolgee")
    print()

    # Step 3: Compute diff
    print("[3/5] Computing diff...")
    new_keys, fills = compute_diff(local, tolgee)
    print(f"  New keys to create: {len(new_keys)}")
    print(f"  Missing translations to fill: {len(fills)}")

    # Breakdown by language
    if fills:
        lang_counts = {}
        for f in fills:
            lang_counts[f["lang"]] = lang_counts.get(f["lang"], 0) + 1
        breakdown = ", ".join(f"{l}={c}" for l, c in sorted(lang_counts.items()))
        print(f"  Fill breakdown: {breakdown}")
    print()

    if not new_keys and not fills:
        print("Everything is in sync! Nothing to do.")
        return

    # Step 4: Push new keys
    print("[4/5] Creating new keys...")
    created = push_new_keys(new_keys, dry_run=args.dry_run)
    print(f"  {'Would create' if args.dry_run else 'Created'}: {created} keys")
    print()

    # Step 5: Fill missing translations
    print("[5/5] Filling missing translations...")
    filled = fill_translations(fills, dry_run=args.dry_run)
    print(f"  {'Would fill' if args.dry_run else 'Filled'}: {filled} translations")
    print()

    # Summary
    print("=" * 50)
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Summary:")
    print(f"  Local keys:        {local_key_count}")
    print(f"  Tolgee keys:       {tolgee_key_count}")
    print(f"  New keys created:  {created}")
    print(f"  Translations filled: {filled}")
    print("=" * 50)


if __name__ == "__main__":
    main()
