#!/usr/bin/env python3
"""VCMS i18n Translation Sync: ko -> en(pair) -> ja,zh-CN,zh-TW,es"""
import json, os, sys, re, unicodedata, time

LOCALES_DIR = os.environ.get("LOCALES_DIR", "locales/latest")
GLOSSARY_PATH = os.environ.get("GLOSSARY_PATH", "glossary/glossary.json")
SOURCE_LANG = "ko"
PAIR_LANG = "en"
PROPAGATE_LANGS = ["ja", "zh-CN", "zh-TW", "es"]
ALL_TARGET_LANGS = [PAIR_LANG] + PROPAGATE_LANGS
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

def strip_zw(s):
    return ''.join(c for c in s if unicodedata.category(c) not in ('Cf','Mn','Cc'))

def load_json(p):
    with open(p,'r',encoding='utf-8') as f: return json.load(f)

def save_json(p, d):
    with open(p,'w',encoding='utf-8') as f: json.dump(d,f,ensure_ascii=False,indent=2); f.write('\n')

def load_glossary():
    if not os.path.exists(GLOSSARY_PATH): return []
    return load_json(GLOSSARY_PATH).get("terms",[])

def get_path(lang): return os.path.join(LOCALES_DIR, f"{lang}.json")

def cleanup_zw(data):
    cm={}
    for k,v in data.items():
        ck=strip_zw(k)
        if ck not in cm or len(k)<len(cm[ck][0]): cm[ck]=(k,v)
    r={}; seen=set()
    for k in data:
        ck=strip_zw(k)
        if ck not in seen: seen.add(ck); r[ck]=cm[ck][1]
    return r, len(data)-len(r)

def translate_with_claude(texts, src, tgt, glossary):
    if not ANTHROPIC_API_KEY:
        print(f"  WARN: no API key, using TODO markers")
        return {k:f"[TODO:{tgt}] {v}" for k,v in texts.items()}
    import urllib.request, urllib.error
    names={"en":"English","ja":"Japanese","zh-CN":"Simplified Chinese","zh-TW":"Traditional Chinese","es":"Spanish"}
    ghint=""
    if glossary:
        lk="zh" if tgt.startswith("zh") else tgt
        ps=[f"  '{t['ko']}' -> '{t.get(lk,t.get(tgt,''))}'" for t in glossary if t.get(lk) or t.get(tgt)]
        if ps: ghint="GLOSSARY (MUST use):\n"+"\n".join(ps)
    results={}; items=list(texts.items()); bs=30
    for i in range(0,len(items),bs):
        batch=dict(items[i:i+bs])
        prompt=f"""You are a professional translator for a Korean hospitality channel manager SaaS (like SiteMinder/Cloudbeds).
Translate JSON values from Korean to {names.get(tgt,tgt)}.
RULES: Keep keys as-is. Translate values only. Preserve {{placeholders}} and \\n. Use hospitality terms. Return ONLY valid JSON.
{ghint}
JSON:
{json.dumps(batch,ensure_ascii=False,indent=2)}"""
        body=json.dumps({"model":ANTHROPIC_MODEL,"max_tokens":4096,"messages":[{"role":"user","content":prompt}]}).encode()
        req=urllib.request.Request("https://api.anthropic.com/v1/messages",data=body,headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"})
        try:
            with urllib.request.urlopen(req,timeout=120) as resp:
                rd=json.loads(resp.read().decode())
            txt="".join(b["text"] for b in rd.get("content",[]) if b.get("type")=="text").strip()
            if txt.startswith("```"): txt=re.sub(r'^```\w*\n?','',txt); txt=re.sub(r'\n?```$','',txt)
            results.update(json.loads(txt))
            print(f"  Batch {i//bs+1}: {len(batch)} keys -> {tgt}")
        except Exception as e:
            print(f"  Batch {i//bs+1} FAILED: {e}")
            for k,v in batch.items(): results[k]=f"[ERROR:{tgt}] {v}"
        if i+bs<len(items): time.sleep(2)
    return results

def auto_fix(data):
    fx=0; r={}
    for k,v in data.items():
        o=v
        if isinstance(v,str): v=v.rstrip('\n').rstrip(' ')
        if v!=o: fx+=1
        r[k]=v
    return r,fx

def main():
    print("="*60+"\nVCMS i18n Translation Sync\n"+"="*60)
    glossary=load_glossary(); print(f"Glossary: {len(glossary)} terms")
    ko_path=get_path(SOURCE_LANG)
    if not os.path.exists(ko_path):
        print(f"ERROR: {ko_path} not found"); sys.exit(1)
    ko=load_json(ko_path); ko,zw=cleanup_zw(ko); save_json(ko_path,ko)
    print(f"ko.json: {zw} zw-dupes removed, {len(ko)} keys")
    report={"source_keys":len(ko),"languages":{}}
    for lang in ALL_TARGET_LANGS:
        print(f"\n--- {lang} ---")
        path=get_path(lang)
        if os.path.exists(path): data=load_json(path)
        elif lang=="zh-CN" and os.path.exists(get_path("zh")):
            data=load_json(get_path("zh")); print("  Migrated from zh.json")
        else: data={}
        data,zw=cleanup_zw(data)
        if zw: print(f"  {zw} zw-dupes removed")
        missing=[k for k in ko if k not in data]; print(f"  Missing: {len(missing)}")
        tc=0
        if missing:
            tt={k:ko[k] for k in missing}
            if lang==PAIR_LANG: tr=translate_with_claude(tt,"ko",lang,glossary)
            else:
                en=load_json(get_path(PAIR_LANG)) if os.path.exists(get_path(PAIR_LANG)) else {}
                src={k:en.get(k,ko[k]) for k in missing}
                tr=translate_with_claude(src,"en",lang,glossary)
            data.update(tr); tc=len(tr)
        for k in [k for k in data if k not in ko]: del data[k]
        data,fx=auto_fix(data)
        ordered={k:data[k] for k in ko if k in data}
        save_json(path,ordered)
        cov=len(ordered)/len(ko)*100 if ko else 0
        report["languages"][lang]={"keys":len(ordered),"coverage":f"{cov:.1f}%","translated":tc,"auto_fixed":fx}
        print(f"  Saved: {lang}.json ({len(ordered)} keys, {cov:.1f}%)")
    rp=os.path.join(LOCALES_DIR,".sync-report.json"); save_json(rp,report)
    print(f"\nReport: {rp}")
    for l,i in report["languages"].items(): print(f"  {l}: {i['coverage']} +{i['translated']}")
    print("Done")

if __name__=="__main__": main()
