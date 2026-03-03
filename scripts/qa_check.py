#!/usr/bin/env python3
"""VCMS Translation QA - 10 checks with OTA brand enforcement and ES capitalization"""
import json, re, sys, argparse
from pathlib import Path

BLOCK = 'BLOCK'
WARNING = 'WARNING'

BRAND_OFFICIAL = {
    "\uc57c\ub180\uc790": "Yanolja",
    "\uc5ec\uae30\uc5b4\ub54c": "Yeogiottae",
    "\uc5ec\uae30\uc5b4\ub54c \uc0ac\uc7a5\ub2d8\uc571": "Yeogiottae",
    "\uc5ec\uae30\uc5b4\ub54c \ud638\uc2a4\ud2b8\ud558\uc6b0\uc2a4": "Yeogiottae Hosthouse",
    "\uc5ec\uae30\uc5b4\ub54c \ud30c\ud2b8\ub108\uc13c\ud130": "Yeogiottae Partner",
    "\uc544\uace0\ub2e4": "Agoda",
    "\uc5d0\uc5b4\ube44\uc564\ube44": "Airbnb",
    "\ubd80\ud0b9\ub2f7\ucef4": "Bookingdotcom",
    "\uaf00\uc2a4\ud14c\uc774 \ubaa8\ud154": "Coolstay Motel",
    "\uaf00\uc2a4\ud14c\uc774 \ud638\ud154": "Coolstay Hotel",
    "\uaf00\uc2a4\ud14c\uc774 \ud39c\uc158": "Coolstay Pension",
    "\ub5a0\ub098\uc694\ub2f7\ucef4": "Ddnayodotcom",
    "\uc775\uc2a4\ud53c\ub514\uc544": "Expedia",
    "\ub124\uc774\ubc84": "Naver",
    "\uc628\ub2e4 \ud638\ud154 \ud50c\ub7ec\uc2a4": "Onda Hotel Plus",
    "\uc628\ub2e4 \ud39c\uc158 \ud50c\ub7ec\uc2a4": "Onda Pension Plus",
    "\ud2b8\ub9bd\ub2f7\ucef4": "Tripdotcom",
    "\ud2b8\ub9bd\ube44\ud1a0\uc988": "Tripbtoz",
}

BRAND_BAD_TRANSLATIONS = {
    "\uc57c\ub180\uc790": ["\u96c5\u4e50\u4f73", "\u4e50\u4f4f", "\u96c5\u8bfa\u4f73", "\u30e4\u30ce\u30eb\u30b8\u30e3", "let's play"],
    "\uc5ec\uae30\uc5b4\ub54c": ["\u8fd9\u91cc\u600e\u4e48\u6837", "\u8fd9\u91cc\u5982\u4f55", "\u3053\u3053\u306f\u3069\u3046", "how about here", "how is here",
                "como es aqui", "c\u00f3mo es aqu\u00ed", "que tal aqui"],
    "\ub124\uc774\ubc84": ["\u5bfc\u822a", "\u30ca\u30d3", "navegador"],
    "\uc544\uace0\ub2e4": ["\u96c5\u9ad8\u8fbe", "\u963f\u54e5\u8fbe"],
    "\uc5d0\uc5b4\ube44\uc564\ube44": ["\u7a7a\u6c14\u5e8a\u548c\u65e9\u9910"],
    "\ubd80\ud0b9\ub2f7\ucef4": ["\u9884\u8ba2\u7f51", "\u8ba2\u623f\u7f51"],
    "\uaf00\uc2a4\ud14c\uc774": ["\u871c\u4f4f", "\u8702\u871c\u4f4f\u5bbf", "\u30cf\u30cb\u30fc\u30b9\u30c6\u30a4"],
    "\ub5a0\ub098\uc694\ub2f7\ucef4": ["\u51fa\u53d1\u7f51", "\u8d70\u5427\u7f51"],
    "\uc775\uc2a4\ud53c\ub514\uc544": ["\u8fdc\u5f81"],
    "\uc628\ub2e4": ["\u6765\u4e86", "\u6e29\u8fbe"],
    "\ud2b8\ub9bd\ub2f7\ucef4": ["\u65c5\u884c\u7f51"],
    "\ud2b8\ub9bd\ube44\ud1a0\uc988": ["\u65c5\u884c\u8282\u62cd"],
}

ES_GLOSSARY = [
    "paquete", "reserva", "tarifa", "suscripci\u00f3n", "suscripcion", "pago",
    "reembolso", "inventario", "conectar", "sincronizaci\u00f3n", "sincronizacion",
    "notificaci\u00f3n", "notificacion", "disponibilidad", "propiedad", "canal",
    "liquidaci\u00f3n", "liquidacion", "estancia", "monto", "porcentaje",
]


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ========== CHECK 1: Glossary ==========
def check_glossary(ko, tr):
    issues = []
    known = {'en': [
        ('Channel Product','Channel Package'), ('Reservation','Booking'),
        ('Accommodation','Property'), ('Sold Out','Sold'),
        ('Product','Package'), ('Price','Rate'), ('Fee','Rate'),
    ]}
    for lang, checks in known.items():
        if lang not in tr: continue
        for key, val in tr[lang].items():
            for wrong, correct in checks:
                if wrong in val:
                    if wrong == 'Product' and 'product' in key.lower(): continue
                    if wrong in ('Price','Fee') and 'price' in key.lower(): continue
                    # [FIX-1] accommodation in key = entity name, not glossary term
                    if wrong == 'Accommodation' and 'accommodat' in key.lower(): continue
                    issues.append({'severity': BLOCK, 'check': 'glossary_violation',
                        'key': key, 'lang': lang,
                        'message': f'"{wrong}" -> "{correct}"', 'value': val[:100]})
    return issues


# ========== CHECK 2: Brand ==========
def check_brand(ko, tr):
    issues = []
    for lang, data in tr.items():
        if lang == 'ko': continue
        for key, val in data.items():
            for brand_ko, bad_list in BRAND_BAD_TRANSLATIONS.items():
                for bad in bad_list:
                    if bad.lower() in val.lower():
                        official = BRAND_OFFICIAL.get(brand_ko, brand_ko)
                        issues.append({'severity': BLOCK, 'check': 'brand_translated',
                            'key': key, 'lang': lang,
                            'message': f'"{brand_ko}" as "{bad}" -> use "{official}"',
                            'value': val[:100]})
    for key, ko_val in ko.items():
        for brand_ko, official_en in BRAND_OFFICIAL.items():
            if brand_ko not in ko_val: continue
            for lang, data in tr.items():
                if lang == 'ko': continue
                tr_val = data.get(key, "")
                if not tr_val: continue
                if official_en.lower() not in tr_val.lower() and brand_ko in tr_val:
                    issues.append({'severity': BLOCK, 'check': 'brand_not_english',
                        'key': key, 'lang': lang,
                        'message': f'Korean "{brand_ko}" leaked -> use "{official_en}"',
                        'value': tr_val[:100]})
    return issues


# ========== CHECK 3: ES capitalization ==========
def check_es_cap(ko, tr):
    issues = []
    if 'es' not in tr: return issues
    for key, val in tr['es'].items():
        words = val.split()
        for i, w in enumerate(words):
            if i == 0: continue
            cl = w.strip('.,;:!?()').lower()
            if cl in ES_GLOSSARY and w[0].isupper():
                prev = words[i-1] if i > 0 else ""
                if not prev.endswith('.'):
                    issues.append({'severity': WARNING, 'check': 'es_capitalization',
                        'key': key, 'lang': 'es',
                        'message': f'"{w}" should be lowercase mid-sentence',
                        'value': val[:100]})
                    break
    return issues


# ========== CHECK 4: Placeholder ==========
def _normalize_ph(s):
    """{ value } -> {value}"""
    return re.sub(r'\{\s+', '{', re.sub(r'\s+\}', '}', s))


def _extract_top_level_ph(text):
    """Extract top-level placeholder variable names only.
    Skips ICU branch internals like {count, plural, =1 {x} other {y}}.
    Only returns the variable names: e.g. 'count', 'value'."""
    normalized = _normalize_ph(text)
    result = set()
    depth = 0
    i = 0
    n = len(normalized)
    while i < n:
        ch = normalized[i]
        if ch == '{':
            depth += 1
            if depth == 1:
                j = i + 1
                while j < n and normalized[j] not in '{}':
                    j += 1
                inner = normalized[i+1:j].strip()
                if ',' in inner:
                    var_name = inner.split(',')[0].strip()
                    if re.match(r'^\w+$', var_name):
                        result.add(var_name)
                elif re.match(r'^\w+$', inner) and j < n and normalized[j] == '}':
                    result.add(inner)
            i += 1
        elif ch == '}':
            depth = max(0, depth - 1)
            i += 1
        else:
            i += 1
    return result


def check_placeholder(ko, tr):
    """[FIX-2] Compare top-level placeholder vars only, ignore ICU internals and whitespace."""
    issues = []
    for lang, data in tr.items():
        for key in data:
            if key not in ko: continue
            kp = _extract_top_level_ph(ko[key])
            tp = _extract_top_level_ph(data[key])
            if kp - tp:
                issues.append({'severity': BLOCK, 'check': 'placeholder_missing',
                    'key': key, 'lang': lang, 'message': f'Missing: {kp-tp}'})
            if tp - kp:
                issues.append({'severity': WARNING, 'check': 'placeholder_extra',
                    'key': key, 'lang': lang, 'message': f'Extra: {tp-kp}'})
    return issues


# ========== CHECK 5: Newline ==========
def check_newline(ko, tr):
    """[FIX] Only flag when newline count differs by more than 1."""
    issues = []
    for lang, data in tr.items():
        for key in data:
            if key not in ko: continue
            ko_n = ko[key].count('\n')
            tr_n = data[key].count('\n')
            if abs(ko_n - tr_n) > 1:
                issues.append({'severity': WARNING, 'check': 'newline_mismatch',
                    'key': key, 'lang': lang,
                    'message': f'ko:{ko_n} vs {lang}:{tr_n}'})
    return issues


# ========== CHECK 6: Empty ==========
def check_empty(tr):
    issues = []
    for lang, data in tr.items():
        for key, val in data.items():
            if val in ('', None):
                issues.append({'severity': BLOCK, 'check': 'empty',
                    'key': key, 'lang': lang, 'message': 'Empty'})
    return issues


# ========== CHECK 7: AI leak ==========
def check_ai_leak(tr):
    issues = []
    pat = re.compile(
        r"I cannot translate|I'm sorry|Lo siento|Original:|Translation:|"
        r"Note:|Here is|As an AI|\[.*translated.*\]", re.I)
    for lang, data in tr.items():
        for key, val in data.items():
            if pat.search(val):
                issues.append({'severity': BLOCK, 'check': 'ai_leak',
                    'key': key, 'lang': lang, 'message': 'AI prompt leak', 'value': val[:100]})
    return issues


# ========== CHECK 8: HTML ==========
def check_html(ko, tr):
    issues = []
    tag = re.compile(r'<[^>]+>')
    for lang, data in tr.items():
        for key in data:
            if key not in ko: continue
            if sorted(tag.findall(ko[key])) != sorted(tag.findall(data[key])):
                issues.append({'severity': BLOCK, 'check': 'html_broken',
                    'key': key, 'lang': lang,
                    'message': f'Tags mismatch ko={tag.findall(ko[key])}'})
    return issues


# ========== CHECK 9: Untranslated ==========
def _is_variable_only(text):
    """'{value}', '{ count }', '{a, b}' etc."""
    stripped = re.sub(r'\{[^}]*\}', '', text).strip()
    return not stripped or re.match(r'^[\s,.:;/\-]*$', stripped)


def _is_emoji_only(text):
    cleaned = re.sub(r'[\ufe0f\u200d\u20e3\u200b]', '', text).strip()
    if not cleaned:
        return True
    non_emoji = re.sub(r'[^\x00-\x7f]', '', cleaned).strip()
    return len(non_emoji) == 0 and len(cleaned) <= 10


def check_untranslated(ko, tr):
    """[FIX-3] Skip variable-only and emoji-only keys."""
    issues = []
    for lang, data in tr.items():
        for key in data:
            if key not in ko: continue
            if ko[key] == data[key] and len(ko[key]) > 3:
                if not re.match(r'^[A-Z0-9_.\-/]+$', ko[key]):
                    if _is_variable_only(ko[key]): continue
                    if _is_emoji_only(ko[key]): continue
                    issues.append({'severity': WARNING, 'check': 'untranslated',
                        'key': key, 'lang': lang,
                        'message': f'Same as ko: "{ko[key][:50]}"'})
    return issues


# ========== CHECK 10: ICU format ==========
def check_icu_format(ko, tr):
    issues = []
    icu = re.compile(r'\{(\w+),\s*(select|plural|selectordinal)\s*,')
    for lang, data in tr.items():
        for key in data:
            if key not in ko: continue
            ko_m = icu.findall(ko[key])
            tr_m = icu.findall(data[key])
            if ko_m and not tr_m:
                issues.append({'severity': BLOCK, 'check': 'icu_broken',
                    'key': key, 'lang': lang, 'message': f'ICU format lost: {ko_m}'})
            elif ko_m and tr_m:
                if sorted(ko_m) != sorted(tr_m):
                    issues.append({'severity': BLOCK, 'check': 'icu_mismatch',
                        'key': key, 'lang': lang,
                        'message': f'ICU changed: ko={ko_m} vs {lang}={tr_m}'})
    return issues


# ========== Runner ==========
def run_qa(locales_dir, glossary_path=None):
    ko = load_json(Path(locales_dir) / 'ko.json')
    tr = {}
    for lang in ['en', 'ja', 'zh-CN', 'zh', 'es']:
        p = Path(locales_dir) / f'{lang}.json'
        if p.exists(): tr[lang] = load_json(p)

    checks = [
        ("Glossary", lambda: check_glossary(ko, tr)),
        ("OTA Brand", lambda: check_brand(ko, tr)),
        ("ES capitalization", lambda: check_es_cap(ko, tr)),
        ("Placeholder", lambda: check_placeholder(ko, tr)),
        ("Newline", lambda: check_newline(ko, tr)),
        ("Empty", lambda: check_empty(tr)),
        ("AI leak", lambda: check_ai_leak(tr)),
        ("HTML tags", lambda: check_html(ko, tr)),
        ("Untranslated", lambda: check_untranslated(ko, tr)),
        ("ICU format", lambda: check_icu_format(ko, tr)),
    ]

    all_issues = []
    for name, fn in checks:
        print(f'  [{name}]...')
        all_issues.extend(fn())

    blk = [i for i in all_issues if i['severity'] == BLOCK]
    wrn = [i for i in all_issues if i['severity'] == WARNING]
    print(f'\n  BLOCK:{len(blk)} WARNING:{len(wrn)} TOTAL:{len(all_issues)}')
    for i in blk[:10]:
        print(f'  ! [{i["lang"]}] {i["check"]}: {i["key"]}: {i["message"]}')
    return all_issues


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--locales', default='locales/latest')
    p.add_argument('--glossary', default='glossary/glossary.json')
    p.add_argument('--output')
    args = p.parse_args()
    issues = run_qa(args.locales, args.glossary)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(issues, f, ensure_ascii=False, indent=2)
        print(f'Saved: {args.output}')
    sys.exit(1 if [i for i in issues if i['severity'] == BLOCK] else 0)
