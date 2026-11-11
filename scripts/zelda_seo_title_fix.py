#!/usr/bin/env python3
"""Corregge esclusivamente il SEO title Zelda con refuso verificato; backup prima della scrittura."""
import argparse, datetime as dt, json, os
from pathlib import Path
import requests

BASE="https://aivision.altervista.org"
PID=1650
SLUG="zelda-ocarina-of-time-remake-code-negozi-fisico"
OLD="Zelda Ocarina of Time Remake: file oceaniche per il fisco"
NEW="Zelda Ocarina of Time Remake: code oceaniche al lancio fisico"
PLAN=Path("data/zelda_seo_title_plan.json")
BACKUP=Path("data/zelda_seo_title_backup.json")
RESULT=Path("data/zelda_seo_title_result.json")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=["prepare","apply"])
    mode=ap.parse_args().mode
    base=os.getenv("WP_BASE_URL","").rstrip("/").removesuffix("/wp-json")
    user=os.getenv("WP_USERNAME",""); password=os.getenv("WP_APP_PASSWORD","")
    if base!=BASE or not user or not password:
        raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    s=requests.Session(); s.auth=(user,password)
    s.headers["User-Agent"]="AIVision-Zelda-SEO-Fix/1.0"
    url=f"{BASE}/wp-json/wp/v2/posts/{PID}"
    def read():
        r=s.get(url,params={"context":"edit"},timeout=(8,30)); r.raise_for_status(); return r.json()
    if mode=="prepare":
        p=read(); seo=p.get("aivision_seo")
        if p.get("status")!="publish" or p.get("slug")!=SLUG or not isinstance(seo,dict):
            raise RuntimeError("Post, stato o bridge SEO inatteso.")
        if seo.get("seo_title")!=OLD:
            raise RuntimeError("Il SEO title non corrisponde più al refuso verificato; nessuna modifica.")
        after=dict(seo); after["seo_title"]=NEW
        plan={"site":BASE,"id":PID,"slug":SLUG,"modified":p.get("modified"),
              "before":seo,"after":after}
        PLAN.parent.mkdir(parents=True,exist_ok=True)
        PLAN.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")
        BACKUP.write_text(json.dumps({"site":BASE,"id":PID,"slug":SLUG,
            "previous_modified":p.get("modified"),"previous_aivision_seo":seo},
            ensure_ascii=False,indent=2),encoding="utf-8")
        print("Backup SEO salvato; nessuna modifica ancora eseguita.")
        return
    plan=json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("site")!=BASE or plan.get("id")!=PID or plan.get("slug")!=SLUG:
        raise RuntimeError("Piano non valido.")
    p=read(); seo=p.get("aivision_seo")
    if (p.get("status")!="publish" or p.get("slug")!=SLUG
            or p.get("modified")!=plan.get("modified") or seo!=plan.get("before")):
        raise RuntimeError("Post o metadati modificati dopo il backup; stop.")
    r=s.post(url,params={"context":"edit"},json={"aivision_seo":{"seo_title":NEW}},
             timeout=(8,30),allow_redirects=False)
    r.raise_for_status()
    saved=read(); final=saved.get("aivision_seo") or {}
    if final.get("seo_title")!=NEW:
        raise RuntimeError("Il bridge SEO non ha confermato il nuovo titolo.")
    for key in ("seo_description","focus_keyphrase"):
        if final.get(key)!=plan["before"].get(key):
            raise RuntimeError("Un altro campo SEO è cambiato inaspettatamente: "+key)
    result={"status":"updated_and_verified","post_id":PID,"url":saved.get("link"),
            "old_seo_title":OLD,"new_seo_title":NEW,
            "seo_description_preserved":final.get("seo_description")==plan["before"].get("seo_description"),
            "focus_keyphrase_preserved":final.get("focus_keyphrase")==plan["before"].get("focus_keyphrase")}
    RESULT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
