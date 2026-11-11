#!/usr/bin/env python3
"""Disambigua titoli simili senza cambiare URL o contenuti degli articoli."""
from __future__ import annotations
import argparse, datetime as dt, json, os
from pathlib import Path
import requests
BASE="https://aivision.altervista.org"
PLAN=Path("data/similar_titles_plan.json")
BACKUP=Path("data/similar_titles_backup.json")
RESULT=Path("data/similar_titles_result.json")
UPDATES={
554:("anker-maggo-power-bank-2-pro","Anker MagGo Power Bank 2 Pro: raffreddamento attivo e specifiche Qi2.2","Anker MagGo Power Bank 2 Pro: raffreddamento e Qi2.2"),
1753:("anker-maggo-power-bank-2-pro-recensione-caratteristiche","Recensione Anker MagGo Power Bank 2 Pro: prova e limiti d'uso","Recensione Anker MagGo Power Bank 2 Pro: prova e Qi2.2"),
735:("festa-delle-offerte-prime-sconti-tecnologia","Festa delle Offerte Prime 2026: riepilogo delle promozioni tech","Festa Offerte Prime 2026: riepilogo promozioni tech"),
792:("festa-offerte-prime-ultime-ore-sconti-tech","Prime Day ottobre 2026: offerte tech e prezzi dell'ultima giornata","Prime Day ottobre 2026: riepilogo offerte tech"),
813:("gta-vi-xbox-cloud-gaming-senza-pc","GTA VI su Xbox Cloud Gaming: lancio e limiti su PC","GTA VI su Xbox Cloud: disponibilità e limiti PC"),
1756:("gta-6-xbox-cloud-gaming-xbox-one","GTA 6 su Xbox One tramite cloud: compatibilità e requisiti","GTA 6 su Xbox One via cloud: compatibilità"),
1641:("netflix-aumenta-prezzi-italia-nuovo-listino","Netflix Premium in Italia: nuovo prezzo e spesa annuale","Netflix Premium: prezzo e costo annuale"),
1659:("aumenti-prezzi-netflix-italia-nuove-tariffe","Netflix 2026: listino completo e costo degli utenti extra","Netflix Italia 2026: tutti i prezzi e utenti extra"),
964:("apple-home-collection-smart-home-lg-schneider","Apple Home Collection: videocamere LG, serrature e termostati","Apple Home Collection: videocamere e accessori"),
976:("apple-home-collection-accessori-smart-home","Apple Home Collection: Thread, Matter e integrazione con Casa","Apple Home Collection: Matter, Thread e app Casa"),
}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("mode",choices=["prepare","apply"]);mode=ap.parse_args().mode
 base=os.getenv("WP_BASE_URL","").rstrip("/").removesuffix("/wp-json");user=os.getenv("WP_USERNAME","");password=os.getenv("WP_APP_PASSWORD","")
 if base!=BASE or not user or not password: raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
 s=requests.Session();s.auth=(user,password);s.headers["User-Agent"]="AIVision-Similar-Title-Repair/1.0"
 def read(pid):
  r=s.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=(8,30));r.raise_for_status();return r.json()
 if mode=="prepare":
  changes=[]
  for pid,(slug,title,seo_title) in UPDATES.items():
   p=read(pid);seo=p.get("aivision_seo")
   if p.get("status")!="publish" or p.get("slug")!=slug or not isinstance(seo,dict): raise RuntimeError(f"Post {pid}: stato, slug o SEO inatteso.")
   before=(p.get("title") or {}).get("raw") or (p.get("title") or {}).get("rendered") or ""
   after=dict(seo);after["seo_title"]=seo_title
   changes.append({"id":pid,"slug":slug,"modified":p.get("modified"),"before_title":before,"after_title":title,"before_seo":seo,"after_seo":after})
  payload={"site":BASE,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"changes":changes}
  PLAN.parent.mkdir(parents=True,exist_ok=True);PLAN.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
  BACKUP.write_text(json.dumps({"site":BASE,"created_at":payload["created_at"],"posts":[{"id":x["id"],"slug":x["slug"],"title":x["before_title"],"aivision_seo":x["before_seo"]} for x in changes]},ensure_ascii=False,indent=2),encoding="utf-8")
  print("Backup pronto per",len(changes),"titoli.")
  return
 plan=json.loads(PLAN.read_text(encoding="utf-8"))
 if plan.get("site")!=BASE or len(plan.get("changes",[]))!=10: raise RuntimeError("Piano non valido.")
 results=[]
 for row in plan["changes"]:
  live=read(row["id"]);title=(live.get("title") or {}).get("raw") or (live.get("title") or {}).get("rendered") or ""
  if live.get("status")!="publish" or live.get("slug")!=row["slug"] or live.get("modified")!=row["modified"] or title!=row["before_title"] or live.get("aivision_seo")!=row["before_seo"]:
   raise RuntimeError(f"Post {row['id']} cambiato dopo il backup.")
  r=s.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",params={"context":"edit"},json={"title":row["after_title"],"aivision_seo":row["after_seo"]},timeout=(8,35),allow_redirects=False);r.raise_for_status()
  saved=read(row["id"]);saved_title=(saved.get("title") or {}).get("raw") or (saved.get("title") or {}).get("rendered") or ""
  if saved_title!=row["after_title"] or (saved.get("aivision_seo") or {}).get("seo_title")!=row["after_seo"]["seo_title"]: raise RuntimeError(f"Verifica titolo fallita per {row['id']}")
  results.append({"id":row["id"],"slug":row["slug"],"status":"updated_and_verified","title":saved_title})
  print(f"Post {row['id']}: titolo aggiornato e verificato.")
 RESULT.write_text(json.dumps({"completed_at":dt.datetime.now(dt.timezone.utc).isoformat(),"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
 print("Completati:",len(results))
if __name__=="__main__":main()
