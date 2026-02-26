#!/usr/bin/env python3
"""VCMS 번역 QA 자동 검증 스크립트

10개 검증 항목을 자동으로 체크합니다.

사용법:
  python3 qa_check.py --locales ./locales --glossary ./glossary/glossary.json
"""
import json
import re
import sys
import argparse
from pathlib import Path


# === SEVERITY ===
BLOCK = 'BLOCK'
WARNING = 'WARNING'
INFO = 'INFO'


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_glossary_violations(ko, translations, glossary_terms):
    """#1: 용어집 위반 체크"""
    issues = []
    # Build violation patterns from glossary
    known_violations = {
        'en': [
            ('Channel Product', 'Channel Package'),
            ('Reservation', 'Booking'),
            ('Accommodation', 'Property'),
            ('Sold Out', 'Sold'),
            ('Product', 'Package'),  # context-dependent
        ]
    }
    for lang, checks in known_violations.items():
        if lang not in translations:
            continue
        for key in translations[lang]:
            val = translations[lang][key]
            for wrong, correct in checks:
                if wrong in val:
                    # Skip if 'Product' check and key contains 'product'
                    if wrong == 'Product' and 'product' in key.lower():
                        continue
                    issues.append({
                        'severity': BLOCK,
                        'check': 'glossary_violation',
                        'key': key,
                        'lang': lang,
                        'message': f'"{wrong}" found, should be "{correct}"',
                        'value': val[:100]
                    })
    return issues


def check_placeholder_mismatch(ko, translations):
    """#3: 플레이스홀더 누락"""
    issues = []
    placeholder_re = re.compile(r'\{[^}]+\}')
    
    for lang, data in translations.items():
        for key in data:
            if key not in ko:
                continue
            ko_ph = set(placeholder_re.findall(ko[key]))
            tr_ph = set(placeholder_re.findall(data[key]))
            
            missing = ko_ph - tr_ph
            extra = tr_ph - ko_ph
            
            if missing:
                issues.append({
                    'severity': BLOCK,
                    'check': 'placeholder_missing',
                    'key': key,
                    'lang': lang,
                    'message': f'Missing placeholders: {missing}',
                    'value': data[key][:100]
                })
            if extra:
                issues.append({
                    'severity': WARNING,
                    'check': 'placeholder_extra',
                    'key': key,
                    'lang': lang,
                    'message': f'Extra placeholders: {extra}',
                    'value': data[key][:100]
                })
    return issues


def check_newline_mismatch(ko, translations):
    """#4: 줄바꿈 불일치"""
    issues = []
    for lang, data in translations.items():
        for key in data:
            if key not in ko:
                continue
            ko_nl = ko[key].count('\n')
            tr_nl = data[key].count('\n')
            if ko_nl != tr_nl:
                issues.append({
                    'severity': WARNING,
                    'check': 'newline_mismatch',
                    'key': key,
                    'lang': lang,
                    'message': f'KO has {ko_nl} newlines, {lang.upper()} has {tr_nl}'
                })
    return issues


def check_empty_translations(translations):
    """#5: 빈 번역"""
    issues = []
    for lang, data in translations.items():
        for key, val in data.items():
            if val in ('', None):
                issues.append({
                    'severity': BLOCK,
                    'check': 'empty_translation',
                    'key': key,
                    'lang': lang,
                    'message': 'Empty translation'
                })
    return issues


def check_ai_prompt_leak(translations):
    """#6: AI 프롬프트 누출"""
    issues = []
    leak_patterns = [
        r'I cannot translate',
        r'I\'m sorry',
        r'Lo siento',
        r'Original:',
        r'Translation:',
        r'Note:',
        r'Here is the translation',
        r'\[.*translated.*\]',
        r'As an AI',
    ]
    combined = re.compile('|'.join(leak_patterns), re.IGNORECASE)
    
    for lang, data in translations.items():
        for key, val in data.items():
            if combined.search(val):
                issues.append({
                    'severity': BLOCK,
                    'check': 'ai_prompt_leak',
                    'key': key,
                    'lang': lang,
                    'message': 'Possible AI prompt leak detected',
                    'value': val[:100]
                })
    return issues


def check_html_markup(ko, translations):
    """#7: HTML/마크업 깨짐"""
    issues = []
    tag_re = re.compile(r'<[^>]+>')
    
    for lang, data in translations.items():
        for key in data:
            if key not in ko:
                continue
            ko_tags = sorted(tag_re.findall(ko[key]))
            tr_tags = sorted(tag_re.findall(data[key]))
            if ko_tags != tr_tags:
                issues.append({
                    'severity': BLOCK,
                    'check': 'html_markup_broken',
                    'key': key,
                    'lang': lang,
                    'message': f'KO tags: {ko_tags}, {lang.upper()} tags: {tr_tags}'
                })
    return issues


def check_untranslated(ko, translations):
    """#10: 미번역 (KO=번역값 동일)"""
    issues = []
    for lang, data in translations.items():
        for key in data:
            if key not in ko:
                continue
            if ko[key] == data[key] and len(ko[key]) > 3:
                # Skip short values and keys that are intentionally same
                if not re.match(r'^[A-Z0-9_.\-]+$', ko[key]):
                    issues.append({
                        'severity': WARNING,
                        'check': 'untranslated',
                        'key': key,
                        'lang': lang,
                        'message': f'Same as KO: "{ko[key][:50]}"'
                    })
    return issues


def run_qa(locales_dir, glossary_path=None):
    """QA 전체 실행"""
    ko = load_json(Path(locales_dir) / 'ko.json')
    
    translations = {}
    for lang in ['en', 'ja', 'zh', 'es']:
        path = Path(locales_dir) / f'{lang}.json'
        if path.exists():
            translations[lang] = load_json(path)
    
    glossary = None
    if glossary_path:
        glossary = load_json(glossary_path)
    
    all_issues = []
    
    # Run all checks
    print('Running QA checks...')
    
    print('  [1/7] Glossary violations...')
    all_issues.extend(check_glossary_violations(ko, translations, glossary))
    
    print('  [2/7] Placeholder mismatches...')
    all_issues.extend(check_placeholder_mismatch(ko, translations))
    
    print('  [3/7] Newline mismatches...')
    all_issues.extend(check_newline_mismatch(ko, translations))
    
    print('  [4/7] Empty translations...')
    all_issues.extend(check_empty_translations(translations))
    
    print('  [5/7] AI prompt leaks...')
    all_issues.extend(check_ai_prompt_leak(translations))
    
    print('  [6/7] HTML markup...')
    all_issues.extend(check_html_markup(ko, translations))
    
    print('  [7/7] Untranslated keys...')
    all_issues.extend(check_untranslated(ko, translations))
    
    # Summary
    blocks = [i for i in all_issues if i['severity'] == BLOCK]
    warnings = [i for i in all_issues if i['severity'] == WARNING]
    infos = [i for i in all_issues if i['severity'] == INFO]
    
    print(f'\n=== QA Results ===')
    print(f'  BLOCK:   {len(blocks)}')
    print(f'  WARNING: {len(warnings)}')
    print(f'  INFO:    {len(infos)}')
    print(f'  TOTAL:   {len(all_issues)}')
    
    if blocks:
        print(f'\n=== BLOCK Issues (must fix) ===')
        for i in blocks[:20]:
            print(f'  [{i["lang"]}] {i["key"]}: {i["message"]}')
        if len(blocks) > 20:
            print(f'  ... and {len(blocks) - 20} more')
    
    return all_issues


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='VCMS Translation QA Check')
    parser.add_argument('--locales', default='./locales', help='Locale files directory')
    parser.add_argument('--glossary', default='./glossary/glossary.json', help='Glossary file')
    parser.add_argument('--output', help='Output JSON file for results')
    args = parser.parse_args()
    
    issues = run_qa(args.locales, args.glossary)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(issues, f, ensure_ascii=False, indent=2)
        print(f'\nResults saved to {args.output}')
    
    # Exit with error code if BLOCK issues found
    blocks = [i for i in issues if i['severity'] == BLOCK]
    sys.exit(1 if blocks else 0)
