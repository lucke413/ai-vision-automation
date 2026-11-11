#!/usr/bin/env python3
"""Aggiunge intestazioni H2 a sei articoli privi di struttura, con backup e verifica."""
from __future__ import annotations
import argparse, datetime as dt, json, os, re
from pathlib import Path
import requests
BASE="https://aivision.altervista.org"
PLAN=Path("data/missing_h2_plan.json")
BACKUP=Path("data/missing_h2_backup.json")
RESULT=Path("data/missing_h2_result.json")
POSTS={
934:("gta-6-copie-fisiche-esaurite",[(1,"Disponibilità delle copie fisiche e prenotazioni"),(3,"Perché le scorte sono limitate")]),
1304:("call-of-duty-modern-warfare-4-sconto-nintendo-switch-2",[(1,"Prezzo e riscatto del codice digitale"),(3,"Contenuti e modalità di gioco")]),
1348:("mycopunk-analisi-co-op-shooter",[(1,"Ambientazione e struttura delle missioni"),(3,"Combattimento, armi e progressione"),(5,"Cooperativa e ritmo delle partite")]),
1357:("gemini-su-apple-carplay-google-maps",[(1,"Come funziona Gemini su Google Maps e CarPlay"),(3,"Comandi vocali, compatibilità e limiti")]),
1568:("xbox-nano-controller-pad-tascabile-microsoft",[(1,"Design compatto ed ergonomia"),(3,"Comandi, compatibilità e connettività"),(5,"Prezzo e destinatari")]),
1692:("dreame-airstyle-pro-2-recensione-prezzo",[(1,"Accessori e specifiche tecniche"),(3,"Esperienza d'uso e prestazioni dello styling"),(5,"Posizionamento di mercato e limiti")]),
}

def insert_headings(raw, specs):
    if re.search(r"<h2\b",raw,re.I):
        raise RuntimeError("Il contenuto contiene già H2: controllo manuale necessario.")
    marker="<!-- /wp:paragraph -->"
    if marker in raw:
        token=marker
        block='\n<!-- wp:heading {"level":2} --><h2>{}</h2><!-- /wp:heading -->\n'
    else:
        token="</p>"
        block="\n<h2>{}</h2>\n"
    positions=[m.end() for m in re.finditer(re.escape(token),raw,re.I)]
    if len(positions)<max(i for i,_ in specs):
        raise RuntimeError(f"Paragrafi insufficienti: {len(positions)}")
    out=raw
    for idx,heading in sorted(specs,reverse=True):
        pos=positions[idx-1]
        out=out[:pos]+block.format(heading)+out[pos:]
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("mode",choices=["prepare","apply"]);mode=ap.parse_args().mode
    base=os.getenv("WP_BASE_URL","").rstrip("/").removesuffix("/wp-json");user=os.getenv("WP_USERNAME","");password=os.getenv("WP_APP_PASSWORD","")
    if base!=BASE or not user or not password: raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    s=requests.Session();s.auth=(user,password);s.headers["User-Agent"]="AIVision-Missing-H2-Repair/1.0"
    def read(pid):
        r=s.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=(8,30));r.raise_for_status();return r.json()
    if mode=="prepare":
        changes=[]
        for pid,(slug,specs) in POSTS.items():
            p=read(pid);raw=(p.get("content") or {}).get("raw")
            if p.get("status")!="publish" or p.get("slug")!=slug or not isinstance(raw,str):
                raise RuntimeError(f"Post {pid}: stato, slug o contenuto inatteso.")
            after=insert_headings(raw,specs)
            changes.append({"id":pid,"slug":slug,"modified":p.get("modified"),"before":raw,"after":after,"headings":[h for _,h in specs]})
        payload={"site":BASE,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"changes":changes}
        PLAN.parent.mkdir(parents=True,exist_ok=True);PLAN.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        BACKUP.write_text(json.dumps({"site":BASE,"created_at":payload["created_at"],"posts":[{"id":x["id"],"slug":x["slug"],"modified":x["modified"],"content_raw":x["before"]} for x in changes]},ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"Piano pronto: {len(changes)} articoli, {sum(len(x['headings']) for x in changes)} intestazioni H2. Backup completo salvato.")
        return
    plan=json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("site")!=BASE or len(plan.get("changes",[]))!=6: raise RuntimeError("Piano non valido.")
    results=[]
    for row in plan["changes"]:
        live=read(row["id"]);raw=(live.get("content") or {}).get("raw")
        if live.get("status")!="publish" or live.get("slug")!=row["slug"] or live.get("modified")!=row["modified"] or raw!=row["before"]:
            raise RuntimeError(f"Post {row['id']} modificato dopo il backup.")
        r=s.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",params={"context":"edit"},json={"content":row["after"]},timeout=(8,40),allow_redirects=False);r.raise_for_status()
        saved=read(row["id"]);saved_raw=(saved.get("content") or {}).get("raw") or ""
        if saved_raw!=row["after"] or len(re.findall(r"<h2\b",saved_raw,re.I))!=len(row["headings"]):
            raise RuntimeError(f"Verifica H2 fallita per post {row['id']}.")
        results.append({"id":row["id"],"slug":row["slug"],"status":"updated_and_verified","h2_added":len(row["headings"]),"headings":row["headings"]})
        print(f"Post {row['id']}: aggiunte e verificate {len(row['headings'])} intestazioni.")
    RESULT.write_text(json.dumps({"completed_at":dt.datetime.now(dt.timezone.utc).isoformat(),"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Completati:",len(results))
if __name__=="__main__":main()
