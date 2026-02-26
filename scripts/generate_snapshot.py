#!/usr/bin/env python3
"""VCMS 번역 주간 스냅샷 생성기

사용법:
  python3 generate_snapshot.py --locales ./locales --output ./snapshots

매주 실행하여 번역 상태를 추적합니다.
4주 이상된 스냅샷은 자동 삭제됩니다.
"""
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import argparse


def load_locale(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_glossary(ko, en):
    """용어집 위반 체크"""
    violations = []
    checks = [
        ('Channel Product', 'Channel Package'),
        ('Reservation', 'Booking'),
        ('Accommodation', 'Property'),
        ('Sold Out', 'Sold'),
    ]
    for key in ko:
        if key not in en:
            continue
        en_val = en[key]
        for wrong, correct in checks:
            if wrong in en_val:
                violations.append({
                    'key': key,
                    'issue': f'{wrong} → should be {correct}',
                    'current': en_val[:80]
                })
    return violations


def check_es_charlimit(ko, es):
    """ES 글자수 2배 초과 체크"""
    over = []
    for key in ko:
        if key not in es:
            continue
        ko_len = len(ko[key])
        es_len = len(es[key])
        if ko_len > 0 and es_len > ko_len * 2:
            over.append({
                'key': key,
                'ko_len': ko_len,
                'es_len': es_len,
                'ratio': round(es_len / ko_len, 1)
            })
    return sorted(over, key=lambda x: -x['ratio'])


def count_zwc_keys(data):
    """제로위드스 문자 키 카운트"""
    return len([k for k in data if any(
        ord(c) in range(0x200B, 0x200E) or
        ord(c) in range(0xFE00, 0xFE10)
        for c in k
    )])


def cleanup_old_snapshots(snapshots_dir, weeks=4):
    """4주 이상된 스냅샷 삭제"""
    cutoff = datetime.now() - timedelta(weeks=weeks)
    removed = []
    for entry in Path(snapshots_dir).iterdir():
        if not entry.is_dir() or not entry.name.startswith('20'):
            continue
        try:
            # Parse week folder name like 2026-W08
            year, week = entry.name.split('-W')
            folder_date = datetime.strptime(f'{year}-W{week}-1', '%Y-W%W-%w')
            if folder_date < cutoff:
                shutil.rmtree(entry)
                removed.append(entry.name)
        except (ValueError, IndexError):
            continue
    return removed


def generate_snapshot(locales_dir, output_dir):
    """주간 스냅샷 생성"""
    # Load locales
    langs = {}
    for lang in ['ko', 'en', 'ja', 'zh', 'es']:
        path = os.path.join(locales_dir, f'{lang}.json')
        if os.path.exists(path):
            langs[lang] = load_locale(path)

    ko = langs.get('ko', {})
    now = datetime.now()
    week = now.strftime('%Y-W%W')

    # Missing keys
    missing = {}
    for lang in ['en', 'ja', 'zh', 'es']:
        if lang in langs:
            missing[lang] = sorted(set(ko.keys()) - set(langs[lang].keys()))

    # Empty translations
    empty = {}
    for lang in ['en', 'ja', 'zh', 'es']:
        if lang in langs:
            empty[lang] = len([k for k in langs[lang] if langs[lang][k] in ('', None)])

    # Glossary violations
    violations = check_glossary(ko, langs.get('en', {})) if 'en' in langs else []

    # ES charlimit
    es_over = check_es_charlimit(ko, langs.get('es', {})) if 'es' in langs else []

    snapshot = {
        'metadata': {
            'week': week,
            'date': now.strftime('%Y-%m-%d'),
            'expires': '4 weeks from creation'
        },
        'key_counts': {lang: len(data) for lang, data in langs.items()},
        'missing_keys': {
            'total': len(missing.get('en', [])),
            'by_lang': {lang: len(m) for lang, m in missing.items()},
            'keys': missing.get('en', [])
        },
        'empty_translations': empty,
        'glossary_violations': {
            'total': len(violations),
            'items': violations
        },
        'es_charlimit_risk': {
            'total_over_2x': len(es_over),
            'worst_10': es_over[:10]
        },
        'zero_width_char_keys': count_zwc_keys(ko)
    }

    # Save
    week_dir = os.path.join(output_dir, week)
    os.makedirs(week_dir, exist_ok=True)
    out_path = os.path.join(week_dir, 'snapshot.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    # Cleanup old snapshots
    removed = cleanup_old_snapshots(output_dir)

    print(f'Snapshot saved: {out_path}')
    print(f'  KO: {len(ko)} keys')
    print(f'  Missing: {snapshot["missing_keys"]["total"]}')
    print(f'  Glossary violations: {len(violations)}')
    print(f'  ES over 2x: {len(es_over)}')
    if removed:
        print(f'  Cleaned up old snapshots: {removed}')

    return snapshot


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='VCMS Translation Weekly Snapshot')
    parser.add_argument('--locales', default='./locales', help='Locale files directory')
    parser.add_argument('--output', default='./snapshots', help='Snapshots output directory')
    args = parser.parse_args()
    generate_snapshot(args.locales, args.output)
