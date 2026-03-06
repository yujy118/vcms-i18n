#!/usr/bin/env python3
"""VCMS Translation QA - 11 checks with OTA brand enforcement, ES capitalization, and length ratio"""
import json, re, sys, argparse
from pathlib import Path

BLOCK = 'BLOCK'
WARNING = 'WARNING'

# Length ratio thresholds - only for CJK languages
# en/es EXCLUDED: alphabetic scripts are inherently 2-4x longer than Korean syllabic,
# making ratio checks produce massive false positives with zero real bugs.
LENGTH_RATIO_THRESHOLDS = {
    'ja': 1.8,
    'zh': 1.5,
    'zh-TW': 1.5,
}
LENGTH_RATIO_SKIP_LANGS = {'en', 'es'}

BRAND_OFFICIAL = {
    "야놀자": "Yanolja", "여기어때": "Yeogiottae",
    "여기어때 사장님앱": "Yeogiottae", "여기어때 호스트하우스": "Yeogiottae Hosthouse",
    "여기어때 파트너센터": "Yeogiottae Partner",
    "아고다": "Agoda", "에어비앤비": "Airbnb", "부킹닷컴": "Bookingdotcom",
    "쿨스테이 모텔": "Coolstay Motel", "쿨스테이 호텔": "Coolstay Hotel",
    "쿨스테이 펜션": "Coolstay Pension", "떠나요닷컴": "Ddnayodotcom",
    "익스피디아": "Expedia", "네이버": "Naver",
    "온다 호텔 플러스": "Onda Hotel Plus", "온다 펜션 플러스": "Onda Pension Plus",
    "트립닷컴": "Tripdotcom", "트립비토즈": "Tripbtoz",
}

BRAND_BAD_TRANSLATIONS = {
    "야놀자": ["雅乐佳", "乐住", "雅诺佳", "ヤノルジャ", "let's play"],
    "여기어때": ["这里怎么样", "这里如何", "ここはどう", "how about here", "how is here",
                "como es aqui", "cómo es aquí", "que tal aqui"],
    "네이버": ["导航", "ナビ", "navegador"],
    "아고다": ["雅高达", "阿哥达"], "에어비앤비": ["空气床和早餐"],
    "부킹닷컴": ["预订网", "订房网"],
    "쿨스테이": ["蜜住", "蜂蜜住宿", "ハニーステイ"],
    "떠나요닷컴": ["出发网", "走吧网"], "익스피디아": ["远征"],
    "온다": ["来了", "温达"], "트립닷컴": ["旅行网"], "트립비토즈": ["旅行节拍"],
}

ES_GLOSSARY = [
    "paquete", "reserva", "tarifa", "suscripción", "suscripcion", "pago",
    "reembolso", "inventario", "conectar", "sincronización", "sincronizacion",
    "notificación", "notificacion", "disponibilidad", "propiedad", "canal",
    "liquidación", "liquidacion", "estancia", "monto", "porcentaje",
]


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ========== CHECK 1: Glossary ==========
FEE_ALLOWED_PATTERNS = [
    'subscription', 'payment-option', 'extra-adult', 'extra-guest',
    'additional-fee', 'basefee', 'additionalfee',
    'rate-plan', 'terms.service', 'terms.private',
]
PRICE_ALLOWED_PATTERNS = ['price', 'charge.asc', 'charge.desc', 'first-payment']

# Keys where "Accommodation" is correct (refers to the physical property/building,
# not the UI menu item). Onboarding, integration, and setup contexts use Accommodation
# because they describe the lodging establishment itself.
ACCOMMODATION_ALLOWED_PATTERNS = [
    'accommodat', 'onboarding', 'integration', 'create-accommodation',
    'select-property',
]

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
                    if wrong == 'Accommodation':
                        kl = key.lower()
                        if any(p in kl for p in ACCOMMODATION_ALLOWED_PATTERNS): continue
                    if wrong == 'Fee':
                        kl = key.lower()
                        if any(p in kl for p in FEE_ALLOWED_PATTERNS): continue
                        if not re.search(r'\bFee\b', val): continue
                    if wrong == 'Price':
                        kl = key.lower()
                        if any(p in kl for p in PRICE_ALLOWED_PATTERNS): continue
                        val_no_vars = re.sub(r'\{[^}]*\}', '', val)
                        if 'Price' not in val_no_vars: continue
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
                            'message': f'"{brand_ko}" as "{bad}" -> use "{official}"', 'value': val[:100]})
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
                        'message': f'Korean "{brand_ko}" leaked -> use "{official_en}"', 'value': tr_val[:100]})
    return issues


# ========== CHECK 3: ES capitalization ==========
def check_es_cap(ko, tr):
    issues = []
    if 'es' not in tr: return issues
    for key, val in tr['es'].items():
        words = val.split()
        if len(words) < 8: continue
        if not any(w[0].islower() for w in words[1:] if len(w) > 1 and w[0].isalpha()): continue
        for i, w in enumerate(words):
            if i == 0: continue
            cl = w.strip('.,;:!?()').lower()
            if cl in ES_GLOSSARY and w[0].isupper():
                prev = words[i-1] if i > 0 else ""
                if not prev.endswith('.'):
                    issues.append({'severity': WARNING, 'check': 'es_capitalization',
                        'key': key, 'lang': 'es',
                        'message': f'"{w}" should be lowercase mid-sentence', 'value': val[:100]})
                    break
    return issues


# ========== CHECK 4: Placeholder ==========
def _normalize_ph(s):
    return re.sub(r'\{\s+', '{', re.sub(r'\s+\}', '}', s))

def _extract_top_level_ph(text):
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
                while j < n and normalized[j] not in '{}': j += 1
                inner = normalized[i+1:j].strip()
                if ',' in inner:
                    var_name = inner.split(',')[0].strip()
                    if re.match(r'^\w+$', var_name): result.add(var_name)
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
    stripped = re.sub(r'\{[^}]*\}', '', text).strip()
    return not stripped or re.match(r'^[\s,.:;/\-]*$', stripped)

def _is_emoji_only(text):
    cleaned = re.sub(r'[\ufe0f\u200d\u20e3\u200b]', '', text).strip()
    if not cleaned: return True
    non_emoji = re.sub(r'[^\x00-\x7f]', '', cleaned).strip()
    return len(non_emoji) == 0 and len(cleaned) <= 10

def _is_url(text):
    return text.startswith('http://') or text.startswith('https://')

def _is_date_format(text):
    return bool(re.match(r'^[MdyYHhmsEcGaL\s.,:\-/()]+$', text))

def _is_html_variable_only(text):
    stripped = re.sub(r'<[^>]+>', '', text)
    stripped = re.sub(r'\{[^}]*\}', '', stripped).strip()
    return not stripped or re.match(r'^[\s~,.:;/\-+*=|]+$', stripped)

def check_untranslated(ko, tr):
    issues = []
    for lang, data in tr.items():
        for key in data:
            if key not in ko: continue
            if ko[key] == data[key] and len(ko[key]) > 3:
                if not re.match(r'^[A-Z0-9_.\-/]+$', ko[key]):
                    if _is_variable_only(ko[key]): continue
                    if _is_emoji_only(ko[key]): continue
                    if _is_url(ko[key]): continue
                    if _is_date_format(ko[key]): continue
                    if _is_html_variable_only(ko[key]): continue
                    issues.append({'severity': WARNING, 'check': 'untranslated',
                        'key': key, 'lang': lang, 'message': f'Same as ko: "{ko[key][:50]}"'})
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


# ========== CHECK 11: Length ratio (ja/zh only) ==========
def check_length_ratio(ko, tr):
    """WARN if ja/zh translation exceeds threshold vs Korean source.
    en/es skipped: alphabetic scripts are inherently 2-4x longer than Korean."""
    issues = []
    var_re = re.compile(r'\{[^}]+\}')
    tag_re = re.compile(r'<[^>]+>')
    icu_re = re.compile(r'\{[^,}]+,\s*(select|plural|selectordinal)')

    def visible_len(s):
        s = var_re.sub('', s)
        s = tag_re.sub('', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return len(s)

    for lang, data in tr.items():
        if lang in LENGTH_RATIO_SKIP_LANGS:
            continue
        threshold = LENGTH_RATIO_THRESHOLDS.get(lang, 2.0)
        for key in data:
            if key not in ko: continue
            ko_val = ko[key]
            tr_val = data[key]
            ko_vl = visible_len(ko_val)
            if ko_vl < 10: continue
            if icu_re.search(ko_val): continue
            tr_vl = visible_len(tr_val)
            if tr_vl == 0: continue
            ratio = tr_vl / ko_vl
            if ratio > threshold:
                issues.append({
                    'severity': WARNING, 'check': 'length_ratio',
                    'key': key, 'lang': lang,
                    'message': f'ko={ko_vl} vs {lang}={tr_vl} ({ratio:.1f}x, limit {threshold}x)'
                })
    return issues


# ========== Runner ==========
def run_qa(locales_dir, glossary_path=None):
    ko = load_json(Path(locales_dir) / 'ko.json')
    tr = {}
    for lang in ['en', 'ja', 'zh', 'zh-TW', 'es']:
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
        ("Length ratio", lambda: check_length_ratio(ko, tr)),
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
