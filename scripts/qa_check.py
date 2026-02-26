#!/usr/bin/env python3
"""
VCMS i18n QA Validator
Automated quality checks for translation files.
Usage: python qa_check.py [--verbose]
"""
import json, re, sys
from pathlib import Path
from collections import defaultdict

LOCALES_DIR = Path(__file__).parent.parent / "locales"
GLOSSARY_PATH = Path(__file__).parent.parent / "glossary.json"

CHAR_LIMITS = {"button":25,"label":40,"title":50,"tooltip":120,"placeholder":60,"badge":30,"header":50,"error":150}
PROMPT_LEAK_PATTERNS = [r"I cannot translate",r"I'm sorry",r"Lo siento",r"Original:",r"Translation:",r"Here is the translation",r"As an AI"]

class QAResult:
    def __init__(self):
        self.errors, self.warnings, self.info = [], [], []
    def add(self, sev, key, lang, msg):
        {"BLOCK":self.errors,"WARNING":self.warnings}.get(sev, self.info).append({"key":key,"lang":lang,"message":msg})
    def summary(self):
        return {"errors":len(self.errors),"warnings":len(self.warnings),"info":len(self.info),"passed":len(self.errors)==0}

def load_glossary():
    with open(GLOSSARY_PATH,"r",encoding="utf-8") as f: return json.load(f)["terms"]

def load_translations():
    t = {}
    for fp in LOCALES_DIR.glob("*.json"):
        with open(fp,"r",encoding="utf-8") as f: t[fp.stem] = json.load(f)
    return t

def check_missing(t, r):
    ko = set(t.get("ko",{}).keys())
    for l in ["en","ja","zh","es"]:
        if l not in t: continue
        for k in ko - set(t[l].keys()): r.add("BLOCK",k,l,"Missing translation")

def check_empty(t, r):
    for l,d in t.items():
        for k,v in d.items():
            if not v or not v.strip(): r.add("BLOCK",k,l,"Empty translation")

def check_placeholders(t, r):
    p = re.compile(r"\{[^}]+\}")
    for k,v in t.get("ko",{}).items():
        kp = set(p.findall(v))
        if not kp: continue
        for l in ["en","ja","zh","es"]:
            if l not in t or k not in t[l]: continue
            lp = set(p.findall(t[l][k]))
            for m in kp-lp: r.add("BLOCK",k,l,f"Missing placeholder: {m}")

def check_html(t, r):
    p = re.compile(r"</?[a-zA-Z0-9]+>")
    for k,v in t.get("ko",{}).items():
        kt = sorted(p.findall(v))
        if not kt: continue
        for l in ["en","ja","zh","es"]:
            if l not in t or k not in t[l]: continue
            if kt != sorted(p.findall(t[l][k])): r.add("BLOCK",k,l,"HTML tag mismatch")

def check_prompt_leak(t, r):
    for l,d in t.items():
        if l=="ko": continue
        for k,v in d.items():
            for pat in PROMPT_LEAK_PATTERNS:
                if re.search(pat,v,re.I): r.add("BLOCK",k,l,f"Prompt leak: {pat}"); break

def check_glossary(t, r):
    g = load_glossary()
    ko = t.get("ko",{}); en = t.get("en",{})
    wrongs = {"Channel Package":["Channel Product"],"Package":["Product"],"Day-use":["Hourly room"],"Check-in":["Checkin"]}
    for term in g:
        if "context" in term.get("note","").lower(): continue
        for k,kv in ko.items():
            if term["ko"] in kv and k in en:
                for w in wrongs.get(term["en"],[]):
                    if w in en[k] and term["en"] not in en[k]:
                        r.add("BLOCK",k,"en",f"Glossary: '{w}' should be '{term['en']}'")

def run_all(verbose=False):
    print("VCMS i18n QA Validator\n" + "="*60)
    t = load_translations(); r = QAResult()
    for name,fn in [("Missing",check_missing),("Empty",check_empty),("Placeholders",check_placeholders),("HTML",check_html),("Prompt Leak",check_prompt_leak),("Glossary",check_glossary)]:
        b = len(r.errors)
        fn(t,r)
        print(f"  {'✅' if len(r.errors)==b else '❌'} {name}: {len(r.errors)-b} errors")
    s = r.summary()
    print(f"\n{'PASS ✅' if s['passed'] else 'FAIL ❌'} | Errors:{s['errors']} Warnings:{s['warnings']}")
    if verbose:
        for e in r.errors[:50]: print(f"  [{e['lang']}] {e['key']}: {e['message']}")
    return r

if __name__=="__main__":
    r = run_all("--verbose" in sys.argv or "-v" in sys.argv)
    sys.exit(0 if r.summary()["passed"] else 1)