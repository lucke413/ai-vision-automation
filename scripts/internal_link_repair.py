#!/usr/bin/env python3
"""Aggiunge link interni contestuali a quattro articoli, con piano e backup preventivi."""
from __future__ import annotations
import argparse, datetime as dt, json, os
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests

BASE = "https://aivision.altervista.org"
PLAN = Path("data/internal_link_repair_plan.json")
BACKUP = Path("data/internal_link_repair_backup.json")
RESULT = Path("data/internal_link_repair_result.json")
REPAIRS = {
  940: {
    "slug": "soundpeats-cove-pro-offerta-aliexpress",
    "links": [
      ("Sony WH-CH730N: cuffie wireless", "https://aivision.altervista.org/sony-wh-ch730n-recensione-caratteristiche/"),
      ("guida alle migliori cuffie Bluetooth senza fili", "https://aivision.altervista.org/migliori-cuffie-bluetooth-senza-fili/"),
    ],
    "intro": "Per confrontare altri modelli e orientarti tra le alternative",
  },
  1423: {
    "slug": "gta-6-sondaggio-record-previsioni-vendita",
    "links": [
      ("le prestazioni di GTA 6 su console", "https://aivision.altervista.org/gta-6-girera-a-30-fps-su-console-rockstar-conferma/"),
      ("il pre-download di GTA 6 su PS5", "https://aivision.altervista.org/grand-theft-auto-vi-pre-download-ps5-10-novembre/"),
    ],
    "intro": "Per seguire gli altri aggiornamenti in vista del lancio",
  },
  1650: {
    "slug": "zelda-ocarina-of-time-remake-code-negozi-fisico",
    "links": [
      ("l'analisi della nuova edizione di Ocarina of Time", "https://aivision.altervista.org/the-legend-of-zelda-ocarina-of-time-switch-2-analisi/"),
      ("i risultati del lancio di Zelda su Switch 2", "https://aivision.altervista.org/nintendo-switch-2-vendite-zelda-ocarina-of-time/"),
    ],
    "intro": "Per approfondire il ritorno di Zelda su Switch 2",
  },
  1644: {
    "slug": "oppo-find-x10-e-pro-max-sconto-store-ufficiale",
    "links": [
      ("POCO X8s, lo smartphone compatto appena arrivato in Italia", "https://aivision.altervista.org/poco-x8s-italia-prezzo-specifiche-promo-lancio/"),
      ("Google Pixel 11 da 512 GB", "https://aivision.altervista.org/google-pixel-11-offerta-729-euro-amazon/"),
    ],
    "intro": "Se stai confrontando smartphone di fascia alta e alternative",
  },
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["prepare", "apply"])
    args = ap.parse_args()
    base = os.getenv("WP_BASE_URL", "").rstrip("/").removesuffix("/wp-json")
    user, password = os.getenv("WP_USERNAME", ""), os.getenv("WP_APP_PASSWORD", "")
    if base != BASE or not user or not password:
        raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    s = requests.Session()
    s.auth = (user, password)
    s.headers["User-Agent"] = "AIVision-Internal-Link-Repair/1.0"
    def get_post(pid):
        r=s.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=(8,30))
        r.raise_for_status(); return r.json()
    def check_destination(url):
        p=urlsplit(url)
        if p.scheme!="https" or p.netloc!="aivision.altervista.org" or p.query or p.fragment:
            raise ValueError("Destinazione non interna o non consentita: "+url)
        r=s.get(url,timeout=(8,25),allow_redirects=True)
        if r.status_code!=200 or urlsplit(r.url).netloc!="aivision.altervista.org":
            raise RuntimeError(f"Destinazione non valida ({r.status_code}): {url}")
        return r.url
    if args.mode=="prepare":
        rows=[]
        for pid, spec in REPAIRS.items():
            p=get_post(pid)
            if p.get("status")!="publish" or p.get("slug")!=spec["slug"]:
                raise RuntimeError(f"Post {pid}: stato o slug inatteso; stop.")
            raw=(p.get("content") or {}).get("raw")
            if not isinstance(raw,str) or not raw.strip():
                raise RuntimeError(f"Post {pid}: contenuto raw non disponibile.")
            validated=[]
            for label,url in spec["links"]:
                final=check_destination(url)
                validated.append((label,final))
            missing_links = [(label,url) for label,url in validated if url not in raw]
            if not missing_links:
                print(f"Post {pid}: link interni già presenti; nessuna modifica necessaria.")
                continue
            paragraph = "<p>" + spec["intro"] + ": " + " e ".join(
                f'<a href="{url}">{label}</a>' for label,url in missing_links
            ) + ".</p>"
            after=raw.rstrip()+"\n\n"+paragraph
            rows.append({"id":pid,"slug":spec["slug"],"modified":p.get("modified"),
                         "before":raw,"after":after,"links":[{"label":l,"url":u} for l,u in missing_links]})
        payload={"site":BASE,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"changes":rows}
        PLAN.parent.mkdir(parents=True,exist_ok=True)
        PLAN.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        BACKUP.write_text(json.dumps({"site":BASE,"created_at":payload["created_at"],
            "posts":[{"id":r["id"],"slug":r["slug"],"modified":r["modified"],"content_raw":r["before"]}
                     for r in rows]},ensure_ascii=False,indent=2),encoding="utf-8")
        print("Piano pronto. Quattro post, otto destinazioni verificate HTTP 200. Nessuna modifica ancora eseguita.")
        return
    plan=json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("site")!=BASE or not (1 <= len(plan.get("changes",[])) <= 4):
        raise RuntimeError("Piano mancante o non valido.")
    results=[]
    for row in plan["changes"]:
        live=get_post(row["id"])
        raw=(live.get("content") or {}).get("raw")
        if (live.get("status")!="publish" or live.get("slug")!=row["slug"]
                or live.get("modified")!=row["modified"] or raw!=row["before"]):
            raise RuntimeError(f"Post {row['id']} modificato dopo il backup: stop senza sovrascrivere.")
        # Revalidate destinations immediately before each write.
        for link in row["links"]:
            check_destination(link["url"])
        response=s.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",
            json={"content":row["after"]},timeout=(8,30),allow_redirects=False)
        response.raise_for_status()
        saved=get_post(row["id"])
        saved_raw=(saved.get("content") or {}).get("raw")
        if saved_raw!=row["after"]:
            raise RuntimeError(f"Verifica fallita sul post {row['id']}.")
        results.append({"id":row["id"],"slug":row["slug"],"status":"updated_and_verified",
                        "links":row["links"]})
        print(f"Post {row['id']}: link interni aggiornati e verificati.")
    RESULT.write_text(json.dumps({"completed_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "results":results},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Completati e verificati:",len(results))

if __name__=="__main__":
    main()
