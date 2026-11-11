#!/usr/bin/env python3
"""Compila le meta description mancanti dai contenuti reali, senza inventare dettagli."""
from __future__ import annotations
import argparse, datetime as dt, html, json, os, re
from pathlib import Path
import requests
BASE="https://aivision.altervista.org"
POST_IDS=[1671,1674,1677,1680,1683,1686,1689,1692,1696,1699,1702,1705,1708,1711,1714,1717,1720,1723,1726,1729,1732,1735,1738,1741,1744,1747,1750,1753,1756,1759,1768]
PLAN=Path("data/missing_meta_descriptions_plan.json")
BACKUP=Path("data/missing_meta_descriptions_backup.json")
RESULT=Path("data/missing_meta_descriptions_result.json")

def plain(s):
    s=html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return " ".join(s.replace("\xa0"," ").split())

def description(title, content, excerpt):
    source=plain(excerpt) or plain(content)
    if not source:
        raise RuntimeError(f"Contenuto vuoto per: {title}")
    # Use only the opening editorial text, never a fabricated claim or a source footer.
    source=re.split(r"\b(?:Leggi anche|Fonti?:|Fonte:|Riferimenti:)\b",source,flags=re.I)[0].strip()
    candidate=source
    if len(candidate)<135:
        candidate=(title.rstrip(".")+". "+candidate).strip()
    if len(candidate)<=160:
        return candidate
    # Prefer a complete sentence within the recommended length.
    stops=[m.end() for m in re.finditer(r"[.!?](?:\s|$)",candidate)]
    good=[n for n in stops if 135<=n<=160]
    if good:
        return candidate[:good[0]].strip()
    cut=candidate[:157].rsplit(" ",1)[0].rstrip(" ,;:-")
    return cut+"…"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("mode",choices=["prepare","apply"]);mode=ap.parse_args().mode
    base=os.getenv("WP_BASE_URL","").rstrip("/").removesuffix("/wp-json")
    user=os.getenv("WP_USERNAME","");password=os.getenv("WP_APP_PASSWORD","")
    if base!=BASE or not user or not password: raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    s=requests.Session();s.auth=(user,password);s.headers["User-Agent"]="AIVision-Meta-Description-Repair/1.0"
    def read(pid):
        r=s.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=(8,30));r.raise_for_status();return r.json()
    if mode=="prepare":
        changes=[]
        for pid in POST_IDS:
            p=read(pid)
            if p.get("status")!="publish": raise RuntimeError(f"Post {pid} non pubblicato.")
            seo=p.get("aivision_seo")
            if not isinstance(seo,dict): raise RuntimeError(f"Post {pid}: campi SEO non accessibili.")
            old=(seo.get("seo_description") or "").strip()
            if old:
                print(f"Post {pid}: descrizione già presente, saltato.")
                continue
            title=plain((p.get("title") or {}).get("raw") or (p.get("title") or {}).get("rendered") or "")
            content=(p.get("content") or {}).get("raw") or (p.get("content") or {}).get("rendered") or ""
            excerpt=(p.get("excerpt") or {}).get("raw") or (p.get("excerpt") or {}).get("rendered") or ""
            desc=description(title,content,excerpt)
            if not (120<=len(desc)<=160): raise RuntimeError(f"Meta description fuori misura per post {pid}: {len(desc)}")
            after=dict(seo);after["seo_description"]=desc
            changes.append({"id":pid,"slug":p.get("slug"),"modified":p.get("modified"),
                "before_seo":seo,"after_seo":after,"description":desc})
        payload={"site":BASE,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"changes":changes}
        PLAN.parent.mkdir(parents=True,exist_ok=True);PLAN.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        BACKUP.write_text(json.dumps({"site":BASE,"created_at":payload["created_at"],
            "posts":[{"id":x["id"],"slug":x["slug"],"modified":x["modified"],"aivision_seo":x["before_seo"]} for x in changes]},
            ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"Piano pronto: {len(changes)} meta description mancanti, tutte ricavate dagli incipit reali.")
        return
    plan=json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("site")!=BASE: raise RuntimeError("Piano non valido.")
    if not plan.get("changes"):
        print("Nessuna meta description da aggiornare: tutti i post selezionati hanno già una descrizione.")
        return
    results=[]
    for row in plan["changes"]:
        live=read(row["id"])
        if live.get("status")!="publish" or live.get("slug")!=row["slug"] or live.get("modified")!=row["modified"] or live.get("aivision_seo")!=row["before_seo"]:
            raise RuntimeError(f"Post {row['id']} modificato dopo il backup; stop.")
        r=s.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",params={"context":"edit"},
            json={"aivision_seo":row["after_seo"]},timeout=(8,35),allow_redirects=False);r.raise_for_status()
        saved=read(row["id"]);final=saved.get("aivision_seo") or {}
        if final.get("seo_description")!=row["description"]: raise RuntimeError(f"Meta description non verificata per post {row['id']}.")
        results.append({"id":row["id"],"slug":row["slug"],"status":"updated_and_verified",
            "length":len(row["description"]),"description":row["description"]})
        print(f"Post {row['id']}: meta description salvata e verificata ({len(row['description'])} caratteri).")
    RESULT.write_text(json.dumps({"completed_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "updated":len(results),"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Completate:",len(results))

if __name__=="__main__":main()
