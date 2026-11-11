#!/usr/bin/env python3
"""Completa due articoli troppo brevi e le relative meta SEO, con backup e verifica."""
from __future__ import annotations
import argparse, datetime as dt, html, json, os, re
from pathlib import Path
import requests

BASE = "https://aivision.altervista.org"
PLAN = Path("data/short_articles_plan.json")
BACKUP = Path("data/short_articles_backup.json")
RESULT = Path("data/short_articles_result.json")
UPDATES = {
  465: {
    "slug": "sonos-beam-ultra-e-ace-ultra-arrivano-nei-negozi",
    "title": "Sonos Beam Ultra e Ace Ultra: prezzi, caratteristiche e Sonos 27",
    "seo": {
      "seo_title": "Sonos Beam Ultra e Ace Ultra: prezzi e novità",
      "seo_description": "Sonos Beam Ultra offre Dolby Atmos 7.1.2; Ace Ultra integra ANC adattiva e 35 ore di autonomia. Prezzi italiani e funzioni di Sonos 27.",
      "focus_keyphrase": "Sonos Beam Ultra"
    },
    "min_words": 380,
    "content": """<p>Sonos amplia la propria gamma con due prodotti pensati per momenti d'ascolto diversi ma collegati dallo stesso ecosistema: la soundbar Beam Ultra, destinata all'home theater, e le cuffie over-ear Ace Ultra. Il lancio è accompagnato da Sonos 27, l'aggiornamento della piattaforma software che punta a rendere più semplice il passaggio tra musica, film e ascolto personale. La disponibilità generale in Italia è partita il 29 settembre 2026.</p>
<h2>Beam Ultra: Dolby Atmos 7.1.2 in un formato compatto</h2>
<p>La nuova soundbar conserva l'impostazione relativamente compatta della famiglia Beam, ma cambia l'architettura acustica. Sonos dichiara nove driver personalizzati, compresi due altoparlanti orientati verso l'alto (up-firing), utilizzati per ricreare un campo sonoro Dolby Atmos 7.1.2. Il canale centrale è stato riprogettato per rendere più comprensibili i dialoghi, un aspetto importante soprattutto nei film e nelle serie in cui musica ed effetti possono coprire le voci.</p>
<p>La gestione dell'audio parlato può essere regolata con AI Speech Enhancement, che offre quattro livelli di intervento. Per la sera è presente Night Sound, pensata per attenuare i picchi più forti senza rinunciare del tutto ai dettagli. Beam Ultra può inoltre essere il punto di partenza di un impianto più ampio: si possono aggiungere un subwoofer per rinforzare le basse frequenze e diffusori posteriori compatibili per creare un sistema surround. La calibrazione Trueplay adatta la resa acustica alla stanza, così la posizione dei mobili e le caratteristiche dell'ambiente incidono meno sul risultato finale.</p>
<h2>Ace Ultra: cancellazione del rumore e collegamento diretto</h2>
<p>Le Sonos Ace Ultra sono cuffie over-ear premium con driver personalizzati da 40 mm e cancellazione attiva del rumore adattiva. Il sistema utilizza dieci microfoni e la batteria è accreditata di un'autonomia fino a 35 ore con ANC attivata: il dato dichiarato va considerato come valore massimo, perché volume, codec e funzioni utilizzate possono modificarlo nell'uso quotidiano.</p>
<p>La caratteristica più distintiva è Headphone Engine 2. In versione Early Access, questa tecnologia permette di trasferire alle cuffie l'audio riprodotto da un impianto Sonos compatibile con la pressione di un tasto, senza dover avviare manualmente una nuova sorgente dallo smartphone. Un secondo comando riporta l'ascolto agli speaker. TrueCinema interviene invece quando le cuffie ricevono il suono da una soundbar compatibile, cercando di ricreare un'esperienza più vicina a quella dell'impianto domestico.</p>
<h2>Connettività, Sonos 27 e prezzi italiani</h2>
<p>Beam Ultra supporta Wi-Fi, Bluetooth e HDMI eARC; Ace Ultra aggiunge USB-C e ingresso analogico da 3,5 mm. La piattaforma Sonos dichiara il supporto a oltre 100 servizi di streaming e permette di raggruppare i diffusori per l'ascolto multi-room. Trueplay è dedicata alla calibrazione della soundbar, mentre l'integrazione delle cuffie estende l'ecosistema anche all'ascolto individuale.</p>
<p>Al lancio italiano il prezzo consigliato era di 699 euro per Sonos Beam Ultra e 449 euro per Sonos Ace Ultra. Le colorazioni principali sono bianco e nero; la variante agave è stata indicata come esclusiva di alcuni canali retail. Si tratta di prezzi di listino comunicati per il lancio, non di una garanzia sul prezzo corrente: offerte e disponibilità possono cambiare presso i rivenditori.</p>
<h2>Quale dei due prodotti ha più senso?</h2>
<p>Beam Ultra è la scelta da valutare se l'obiettivo è migliorare l'audio del televisore, ottenere dialoghi più leggibili e costruire gradualmente un sistema surround. Ace Ultra è più indicata per chi ascolta spesso in cuffia e possiede già altri dispositivi Sonos, perché il trasferimento dell'audio è il vantaggio che la distingue maggiormente dalle normali cuffie Bluetooth. Chi non utilizza l'ecosistema del marchio dovrebbe confrontare con attenzione prezzo, comfort, qualità ANC e compatibilità prima dell'acquisto. Per chi sta valutando anche cuffie più economiche, può essere utile il confronto con le <a href="https://aivision.altervista.org/soundpeats-cove-pro-offerta-aliexpress/">SoundPEATS Cove Pro</a>.</p>"""
  },
  478: {
    "slug": "iphone-18-pro-recensione-novita",
    "title": "iPhone 18 Pro: caratteristiche, fotocamera e chip A20 Pro",
    "seo": {
      "seo_title": "iPhone 18 Pro: fotocamera, A20 Pro e prezzi",
      "seo_description": "iPhone 18 Pro introduce fotocamera Fusion da 48 MP con diaframma variabile, chip A20 Pro a 2 nm e una nuova camera di vapore.",
      "focus_keyphrase": "iPhone 18 Pro"
    },
    "min_words": 420,
    "content": """<p>Con iPhone 18 Pro e iPhone 18 Pro Max, Apple ha concentrato gli aggiornamenti soprattutto su fotocamera, prestazioni sostenute e funzioni software. L'aspetto esterno resta riconoscibile, ma sotto la scocca arrivano il chip A20 Pro a 2 nanometri, un sistema di raffreddamento riprogettato e una fotocamera principale con diaframma variabile. I due modelli sono stati presentati il 9 settembre 2026 e sono arrivati nei negozi italiani il 18 settembre.</p>
<h2>Fotocamera principale da 48 MP con apertura variabile</h2>
<p>La novità fotografica più rilevante è la fotocamera principale Fusion da 48 megapixel, che introduce il controllo del diaframma su iPhone. Il meccanismo utilizza sei lamelle tagliate al laser e permette di passare fra quattro impostazioni di apertura. Apple indica valori che arrivano a f/1,48 per favorire l'ingresso della luce, f/1,8 per i ritratti e f/4 per aumentare la profondità di campo, ad esempio nelle fotografie di gruppo.</p>
<p>La regolazione può essere automatica oppure gestita manualmente attraverso i Pro controls, che raccolgono nell'app Fotocamera parametri come apertura, tempo di scatto e bilanciamento del bianco. È disponibile anche un istogramma per controllare l'esposizione. Per chi registra video, Apple segnala la possibilità di applicare effetti Cinema dopo la ripresa ai filmati fino a 60 fotogrammi al secondo e di realizzare time-lapse in 4K Dolby Vision HDR.</p>
<h2>A20 Pro e raffreddamento: l'obiettivo è mantenere le prestazioni</h2>
<p>Il chip A20 Pro è prodotto con processo a 2 nanometri e integra una CPU a sei core, una GPU a sette core e un Dual Neural Engine a 16 core. Secondo i dati diffusi da Apple, la banda di memoria aumenta del 50% rispetto ad A19 Pro e la GPU può essere fino al 40% più veloce nel rendering grafico. Il Neural Engine è pensato anche per accelerare i modelli di intelligenza artificiale eseguiti direttamente sul dispositivo e le elaborazioni della fotografia computazionale.</p>
<p>La potenza di picco, però, non racconta da sola l'esperienza nell'uso prolungato. Per questo Apple ha ridisegnato il sistema termico introducendo una camera di vapore con superficie tre volte più ampia rispetto a quella di iPhone 17 Pro. Il produttore dichiara un miglioramento fino al 40% nelle prestazioni sostenute rispetto alla generazione precedente. Il vantaggio potenziale riguarda soprattutto sessioni di gioco, registrazioni video e attività che mantengono processore e grafica sotto carico per diversi minuti.</p>
<h2>Dynamic Island, iOS 27 e funzioni legate all'intelligenza artificiale</h2>
<p>La Dynamic Island è stata riprogettata per mostrare fino a tre attività in tempo reale contemporaneamente; Face ID continua a essere disponibile per sblocco e autenticazione. Con iOS 27 arrivano inoltre nuove funzioni di Apple Intelligence, strumenti di modifica delle immagini e Apple Reference Image. Quest'ultima crea un'immagine di riferimento associata ai dati originali del sensore, utile per confrontare lo scatto con eventuali versioni modificate. Apple indica anche un futuro supporto ai metadati e allo standard SynthID per aiutare a riconoscere immagini generate o alterate con l'AI.</p>
<h2>Prezzi, memoria e disponibilità</h2>
<p>In Italia iPhone 18 Pro parte da 1.489 euro, mentre iPhone 18 Pro Max parte da 1.639 euro. Le configurazioni di memoria indicate da Apple sono 256 GB, 512 GB, 1 TB e 2 TB; le colorazioni sono nero, argento, ghiacciaio e borgogna. I prezzi di listino possono variare in base a promozioni, rivenditore e configurazione scelta.</p>
<h2>Vale la pena scegliere il modello Pro?</h2>
<p>La fotocamera con apertura variabile è la novità più concreta per chi scatta spesso e vuole intervenire sulla profondità di campo senza affidarsi soltanto all'elaborazione software. A20 Pro e camera di vapore puntano invece a rendere più costanti le prestazioni nei carichi prolungati, mentre le funzioni di autenticità delle immagini aggiungono un elemento interessante per chi crea e condivide contenuti. Chi usa soprattutto messaggistica, social e navigazione potrebbe non sfruttare tutte queste novità: in quel caso conviene confrontare il prezzo con altri smartphone di fascia alta, come <a href="https://aivision.altervista.org/oppo-find-x10-e-pro-max-sconto-store-ufficiale/">OPPO Find X10 e Find X10 Pro Max</a>, valutando dimensioni, fotocamera, autonomia e durata del supporto software.</p>"""
  }
}

def plain(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())

def words(s):
    return len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ]+(?:['’][\wÀ-ÖØ-öø-ÿ]+)*\b", plain(s)))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=["prepare","apply"])
    mode=ap.parse_args().mode
    base=os.getenv("WP_BASE_URL","").rstrip("/").removesuffix("/wp-json")
    user=os.getenv("WP_USERNAME",""); password=os.getenv("WP_APP_PASSWORD","")
    if base!=BASE or not user or not password:
        raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    s=requests.Session(); s.auth=(user,password)
    s.headers["User-Agent"]="AIVision-Short-Article-SEO-Repair/1.0"
    def read(pid):
        r=s.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=(8,30))
        r.raise_for_status(); return r.json()
    if mode=="prepare":
        changes=[]
        for pid,spec in UPDATES.items():
            p=read(pid)
            if p.get("status")!="publish" or p.get("slug")!=spec["slug"]:
                raise RuntimeError(f"Post {pid}: stato o slug inatteso.")
            raw=(p.get("content") or {}).get("raw")
            seo=p.get("aivision_seo")
            if not isinstance(raw,str) or not isinstance(seo,dict):
                raise RuntimeError(f"Post {pid}: contenuto o campi SEO non accessibili.")
            if words(raw)>spec["min_words"]:
                raise RuntimeError(f"Post {pid}: contenuto cambiato, revisione manuale necessaria.")
            for link in re.findall(r'href="(https://aivision\.altervista\.org/[^"]+)"',spec["content"]):
                check=s.get(link,timeout=(8,25),allow_redirects=True)
                if check.status_code!=200 or not check.url.startswith(BASE+"/"):
                    raise RuntimeError(f"Link interno non valido: {link}")
            after_seo=dict(seo)
            after_seo.update(spec["seo"])
            changes.append({"id":pid,"slug":spec["slug"],"modified":p.get("modified"),
                "before_content":raw,"after_content":spec["content"],
                "before_seo":seo,"after_seo":after_seo,
                "before_words":words(raw),"after_words":words(spec["content"])})
        payload={"site":BASE,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"changes":changes}
        PLAN.parent.mkdir(parents=True,exist_ok=True)
        PLAN.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        BACKUP.write_text(json.dumps({"site":BASE,"created_at":payload["created_at"],
            "posts":[{"id":x["id"],"slug":x["slug"],"modified":x["modified"],
                      "content_raw":x["before_content"],"aivision_seo":x["before_seo"]} for x in changes]},
            ensure_ascii=False,indent=2),encoding="utf-8")
        print("Piano pronto: 2 articoli, contenuti e SEO originali salvati, link interni verificati.")
        for x in changes: print(f"Post {x['id']}: {x['before_words']} -> {x['after_words']} parole.")
        return
    plan=json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("site")!=BASE or len(plan.get("changes",[]))!=2:
        raise RuntimeError("Piano o backup non valido.")
    results=[]
    for row in plan["changes"]:
        live=read(row["id"])
        raw=(live.get("content") or {}).get("raw")
        if (live.get("status")!="publish" or live.get("slug")!=row["slug"]
                or live.get("modified")!=row["modified"] or raw!=row["before_content"]
                or live.get("aivision_seo")!=row["before_seo"]):
            raise RuntimeError(f"Post {row['id']} cambiato dopo il backup: stop.")
        r=s.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",params={"context":"edit"},
            json={"content":row["after_content"],"aivision_seo":row["after_seo"]},
            timeout=(8,40),allow_redirects=False)
        r.raise_for_status()
        saved=read(row["id"])
        if (saved.get("content") or {}).get("raw")!=row["after_content"]:
            raise RuntimeError(f"Contenuto non verificato per post {row['id']}.")
        final=saved.get("aivision_seo") or {}
        for key,value in row["after_seo"].items():
            if final.get(key)!=value:
                raise RuntimeError(f"Campo SEO {key} non verificato per post {row['id']}.")
        results.append({"id":row["id"],"slug":row["slug"],"status":"updated_and_verified",
            "before_words":row["before_words"],"after_words":row["after_words"],
            "seo_title":final.get("seo_title"),"seo_description":final.get("seo_description")})
        print(f"Post {row['id']}: contenuto e SEO aggiornati e verificati.")
    RESULT.write_text(json.dumps({"completed_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "results":results},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Completati e verificati:",len(results))

if __name__=="__main__":
    main()
