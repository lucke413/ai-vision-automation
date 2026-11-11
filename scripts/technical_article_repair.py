#!/usr/bin/env python3
"""Rafforza quattro articoli brevi con dati ufficiali e corregge affermazioni superate."""
from __future__ import annotations
import argparse, datetime as dt, html, json, os, re
from pathlib import Path
import requests
BASE="https://aivision.altervista.org"
PLAN=Path("data/technical_articles_plan.json")
BACKUP=Path("data/technical_articles_backup.json")
RESULT=Path("data/technical_articles_result.json")
UPDATES={
560:{
"slug":"vulnerabilita-fortimail-attacchi-zero-day",
"title":"FortiMail: vulnerabilità critica CVE-2026-104286 sfruttata attivamente",
"seo":{"seo_title":"FortiMail CVE-2026-104286: rischio e contromisure","seo_description":"CVE-2026-104286 colpisce FortiMail con una falla critica di path traversal sfruttata attivamente. Versioni coinvolte e misure difensive.","focus_keyphrase":"CVE-2026-104286 FortiMail"},
"max_words":200,
"content":"""<p>Una vulnerabilità critica di Fortinet FortiMail, identificata come CVE-2026-104286, è stata segnalata come attivamente sfruttata in attacchi. Il problema è particolarmente rilevante per le organizzazioni che utilizzano FortiMail per proteggere la posta elettronica aziendale, perché può consentire a un attaccante remoto non autenticato di scrivere file sul sistema sottostante attraverso richieste HTTP o HTTPS appositamente costruite. L'avviso delle autorità di cybersicurezza assegna alla falla un punteggio CVSS 3.1 pari a 9,8 su 10.</p>
<h2>Che cosa permette la vulnerabilità</h2>
<p>La causa tecnica è una gestione insufficiente dei percorsi dei file, classificata come path traversal. In termini pratici, una richiesta manipolata può tentare di uscire dalle directory che l'applicazione dovrebbe consentire di raggiungere e scrivere file in posizioni non previste. La vulnerabilità non richiede necessariamente credenziali valide: per questo l'esposizione di un'interfaccia FortiMail raggiungibile da reti non fidate aumenta il rischio. La possibilità di scrivere file sul sistema può compromettere integrità e disponibilità dell'apparato e può costituire un punto di partenza per ulteriori attività malevole.</p>
<h2>Versioni FortiMail indicate come vulnerabili</h2>
<p>L'avviso pubblicato dalla Cyber Security Agency di Singapore indica come interessate le versioni FortiMail 7.2.0 fino a 7.4.8, 7.6.0 fino a 7.6.6 e 8.0.0 fino a 8.0.1. Gli amministratori devono confrontare la versione effettivamente installata con l'avviso Fortinet PSIRT FG-IR-26-175, perché le condizioni di correzione e gli eventuali workaround dipendono dal ramo software e dalla configurazione. Non è prudente dedurre una versione sicura da un numero di ramo generico o da una nota di rilascio non riferita al prodotto.</p>
<h2>Che cosa devono fare gli amministratori</h2>
<p>La priorità è verificare immediatamente inventario e versione di tutti gli apparati FortiMail esposti, quindi applicare l'aggiornamento correttivo o il workaround indicato direttamente da Fortinet per il ramo interessato. Se l'interfaccia di amministrazione è accessibile da Internet, va limitata alle sole reti e agli indirizzi autorizzati secondo le procedure aziendali. È inoltre opportuno conservare e analizzare i log, verificare gli indicatori di compromissione pubblicati dal produttore e coinvolgere il team di risposta agli incidenti se emergono attività anomale.</p>
<p>Un aggiornamento non sostituisce l'analisi di un apparato che potrebbe essere già stato compromesso: in presenza di indicatori sospetti occorre seguire le istruzioni di incident response del produttore e le procedure interne, evitando di limitarsi a installare una patch e considerare chiuso l'incidente. Le indicazioni operative devono essere ricavate dall'avviso Fortinet aggiornato, non da comandi copiati da fonti non verificate.</p>
<h2>Perché il caso richiede attenzione immediata</h2>
<p>La combinazione di accesso non autenticato, gravità elevata e sfruttamento attivo rende questa vulnerabilità diversa da una normale segnalazione teorica. Le aziende che usano FortiMail dovrebbero trattare la verifica come un'attività urgente, documentare la versione installata e confermare l'applicazione della correzione. Anche gli apparati non direttamente esposti a Internet vanno controllati se raggiungibili da reti interne non adeguatamente segmentate.</p>"""
},
489:{
"slug":"lg-ultragear-evo-gx9-recensione",
"title":"LG UltraGear evo GX9: monitor OLED 5K2K da 39 pollici, specifiche e funzioni",
"seo":{"seo_title":"LG UltraGear evo GX9: OLED 5K2K 39 pollici e 330 Hz","seo_description":"LG UltraGear evo GX9 offre OLED 5K2K da 39 pollici, dual mode 165/330 Hz, risposta 0,03 ms e USB-C da 90 W.","focus_keyphrase":"LG UltraGear evo GX9"},
"max_words":200,
"content":"""<p>LG UltraGear evo GX9, identificato dal codice 39GX950B-B, è un monitor gaming OLED ultrawide da circa 39 pollici progettato per chi cerca un'elevata definizione senza rinunciare a frequenze di aggiornamento molto alte. Il pannello curvo 21:9 utilizza la risoluzione 5K2K, pari a 5.120 x 2.160 pixel, e combina un'ampia superficie di lavoro con una maggiore immersione nei giochi. Non è un semplice monitor 4K più grande: il formato aggiunge spazio orizzontale, utile anche per timeline, finestre affiancate e applicazioni creative.</p>
<h2>OLED 5K2K e qualità dell'immagine</h2>
<p>Il pannello OLED Tandem di quarta generazione offre neri profondi e contrasto elevato. LG dichiara una luminosità di picco fino a 1.500 nit in condizioni di test, copertura DCI-P3 del 99,5% e certificazione VESA DisplayHDR True Black 500. La curvatura 1500R avvolge il campo visivo e rende più naturale seguire l'immagine su tutta la larghezza. La risoluzione elevata porta la densità a 143 pixel per pollice, un valore utile per testi e dettagli fini, ma richiede una scheda grafica adeguata se si vuole giocare alla risoluzione nativa con impostazioni elevate.</p>
<h2>Dual Mode: 165 Hz in 5K2K o 330 Hz a risoluzione ridotta</h2>
<p>La funzione Dual Mode permette di scegliere fra 5K2K a 165 Hz e WFHD a 330 Hz. La prima modalità privilegia dettaglio e spazio visivo; la seconda sacrifica risoluzione per favorire la fluidità nei giochi competitivi. Il tempo di risposta dichiarato è di 0,03 ms GtG. Sono presenti VRR, compatibilità NVIDIA G-SYNC e AMD FreeSync Premium Pro, oltre a strumenti gaming come Black Stabilizer, Dynamic Action Sync e contatore FPS.</p>
<p>È importante distinguere il valore massimo dalla resa ottenibile con qualsiasi PC: per sfruttare 5K2K ad alto refresh servono GPU, connessione e impostazioni adeguate. L'upscaling AI integrato può migliorare la resa di sorgenti a risoluzione inferiore, ma il risultato dipende dal contenuto di partenza e non equivale a renderizzare il gioco nativamente a 5K2K.</p>
<h2>Connessioni e utilizzo con più dispositivi</h2>
<p>La dotazione comprende due HDMI 2.1, una DisplayPort 2.1 UHBR 20, una USB-C con alimentazione fino a 90 W e porte USB aggiuntive. La USB-C permette di collegare un notebook compatibile con un solo cavo per video e alimentazione, riducendo l'ingombro sulla scrivania. Il supporto a Picture-by-Picture e Picture-in-Picture facilita inoltre l'uso di più sorgenti.</p>
<h2>A chi conviene</h2>
<p>GX9 è pensato per appassionati che vogliono un monitor premium per gaming, creazione di contenuti e multitasking. Il formato 21:9 e la risoluzione 5K2K sono interessanti anche per il lavoro, mentre il Dual Mode offre una seconda impostazione dedicata agli e-sport. Prima dell'acquisto bisogna considerare prezzo, spazio disponibile, distanza di visione e potenza del PC: un monitor di questa categoria dà il meglio con una configurazione di fascia alta e non è la scelta più razionale per chi gioca soltanto a 1080p o utilizza una GPU entry-level.</p>"""
},
521:{
"slug":"lego-playstation-1-prezzo-pezzi-accesso-anticipato",
"title":"LEGO PlayStation: set da 1.911 pezzi, prezzo e dettagli della console",
"seo":{"seo_title":"LEGO PlayStation: 1.911 pezzi, prezzo e dettagli del set","seo_description":"Il set LEGO PlayStation 72306 ricrea la console originale con 1.911 pezzi, tasti funzionanti e diorami Gran Turismo e Ape Escape. Prezzo 159,99 euro.","focus_keyphrase":"LEGO PlayStation"},
"max_words":350,
"content":"""<p>Il set LEGO PlayStation 72306 porta in mattoncini la prima console Sony e il suo controller, con una costruzione pensata per i collezionisti adulti e per chi è cresciuto con la prima generazione PlayStation. Il modello è composto da 1.911 pezzi, è destinato a un pubblico dai 18 anni in su e ha un prezzo consigliato di 159,99 euro. L'accesso anticipato per gli iscritti LEGO Insiders è iniziato il 1° ottobre 2026, mentre la disponibilità generale è partita il 4 ottobre: la fase di early access è quindi terminata.</p>
<h2>Una replica della prima PlayStation</h2>
<p>La console ricostruita mantiene la classica forma grigia e il design riconoscibile del sistema originale. Una volta assemblata misura circa 26 centimetri di larghezza, 19 centimetri di profondità e 6 centimetri di altezza, dimensioni che la rendono adatta a una mensola o a una postazione da collezione. Il controller cablato è incluso e può essere collegato alla console, così da riprodurre anche uno degli elementi più iconici dell'hardware originale.</p>
<p>La costruzione non è soltanto una scocca da esposizione: il set integra i pulsanti Open e Power funzionanti. Il vano disco può essere aperto e rivela dettagli nascosti, trasformando il montaggio in una piccola esperienza celebrativa della storia PlayStation. Il livello di dettaglio è pensato per essere apprezzato da vicino, ma il prodotto resta un modello LEGO e non una console elettronica funzionante: non legge dischi e non esegue videogiochi.</p>
<h2>I diorami nascosti di Gran Turismo e Ape Escape</h2>
<p>All'interno della struttura trovano spazio due piccoli diorami ispirati a Gran Turismo e Ape Escape. Sono elementi separabili e personalizzabili che richiamano due esperienze molto diverse dell'era PlayStation: le corse automobilistiche e l'avventura con le scimmiette. Questi dettagli danno al set un valore aggiuntivo per chi conosce i giochi e vuole esporre un riferimento alla propria storia personale con la console.</p>
<h2>Prezzo e disponibilità</h2>
<p>Il prezzo consigliato europeo è di 159,99 euro. Il set è stato messo in vendita attraverso LEGO.com, i LEGO Store e rivenditori selezionati; la disponibilità effettiva può cambiare in base alle scorte e al canale di acquisto. L'accesso anticipato Insiders dal 1° al 3 ottobre richiedeva l'iscrizione al programma gratuito, mentre dal 4 ottobre l'acquisto è stato aperto al pubblico.</p>
<h2>Per chi è pensato</h2>
<p>Il set è indicato soprattutto per adulti, collezionisti e appassionati PlayStation. Con 1.911 pezzi richiede tempo e spazio per il montaggio, ma offre una presenza scenica più importante rispetto a un piccolo gadget. Non è un prodotto per chi cerca una console da usare: è un oggetto da costruire ed esporre, con un prezzo che va valutato in rapporto alla quantità di pezzi, ai dettagli meccanici e al valore nostalgico della licenza.</p>"""
},
536:{
"slug":"recensione-iphone-18-pro-max",
"title":"iPhone 18 Pro Max: A20 Pro, display da 6,9 pollici e autonomia",
"seo":{"seo_title":"iPhone 18 Pro Max: A20 Pro, display e batteria","seo_description":"iPhone 18 Pro Max abbina display OLED da 6,9 pollici, chip A20 Pro, fotocamera Fusion da 48 MP e fino a 43 ore di riproduzione video.","focus_keyphrase":"iPhone 18 Pro Max"},
"max_words":300,
"content":"""<p>iPhone 18 Pro Max è il modello più grande della gamma Pro 2026 e punta soprattutto su schermo, autonomia e prestazioni. Condivide con iPhone 18 Pro il chip A20 Pro e la nuova fotocamera principale Fusion da 48 megapixel con apertura variabile, ma adotta un display più ampio e una batteria che consente tempi di riproduzione dichiarati superiori. La scelta fra i due modelli non dipende quindi soltanto dalla potenza: dimensioni e peso incidono molto sull'esperienza quotidiana.</p>
<h2>Display OLED da 6,9 pollici e design</h2>
<p>Il pannello Super Retina XDR OLED misura 6,9 pollici e offre una risoluzione di 2.868 x 1.320 pixel a 460 ppi. Sono presenti ProMotion con frequenza adattiva fino a 120 Hz, Always-On, HDR e Dynamic Island. Il telaio unibody in alluminio e la protezione Ceramic Shield 2 sulla parte frontale completano un dispositivo che misura 163,4 millimetri in altezza, 78 millimetri in larghezza e 8,75 millimetri di spessore. Il peso è di 249 grammi: un valore da considerare se si utilizza spesso il telefono con una sola mano o lo si porta in tasca.</p>
<h2>Chip A20 Pro e prestazioni</h2>
<p>Il processore A20 Pro integra una CPU a sei core, con due super core e quattro core ad alta efficienza, una GPU a sette core con Neural Accelerator e due Neural Engine a 16 core. La combinazione è pensata per applicazioni impegnative, grafica, elaborazione fotografica e funzioni di intelligenza artificiale eseguite sul dispositivo. La presenza di ray tracing con accelerazione hardware è un ulteriore vantaggio per i giochi compatibili, anche se il risultato dipende dall'ottimizzazione del singolo titolo.</p>
<h2>Fotocamera Fusion da 48 MP con diaframma variabile</h2>
<p>Il sistema fotografico Pro Fusion include una fotocamera principale da 48 megapixel con apertura variabile fra f/1,48, f/1,8, f/2,8 e f/4. La possibilità di intervenire sull'apertura offre un controllo più diretto sulla luce e sulla profondità di campo. Il sistema resta affiancato dagli altri moduli della fotocamera Pro e dalle funzioni di elaborazione computazionale di iOS 27. Per chi registra video, il formato Pro e le modalità HDR consentono di lavorare con file adatti anche a un flusso di post-produzione più evoluto.</p>
<h2>Autonomia: il vantaggio più concreto rispetto al Pro</h2>
<p>Apple dichiara fino a 43 ore di riproduzione video e fino a 38 ore di streaming video per iPhone 18 Pro Max. Il modello Pro più piccolo arriva rispettivamente a 34 e 31 ore nelle stesse categorie di test dichiarate. Non sono valori garantiti nell'uso reale: luminosità, rete mobile, giochi, fotocamera e applicazioni in background possono ridurre l'autonomia. La differenza di capacità è comunque uno dei motivi principali per scegliere il Max, soprattutto per chi guarda molti video o utilizza spesso il telefono lontano da una presa.</p>
<h2>iOS 27 e disponibilità delle funzioni</h2>
<p>iPhone 18 Pro Max viene distribuito con iOS 27 e supporta Apple Intelligence. La disponibilità delle singole funzioni può dipendere da lingua, regione e aggiornamenti software; non è corretto considerare tutte le funzioni di Siri o dell'intelligenza artificiale assenti in Europa in modo generalizzato. Prima di acquistare è meglio controllare le funzioni effettivamente disponibili nella propria lingua e nel proprio Paese.</p>
<h2>Pro Max o Pro?</h2>
<p>Il Pro Max è indicato per chi desidera il display più grande e la migliore autonomia dichiarata, accettando peso e ingombro maggiori. iPhone 18 Pro conserva gran parte delle prestazioni e del comparto fotografico in un formato più compatto e leggero. La scelta dipende quindi dall'uso: schermo e batteria favoriscono il Max, maneggevolezza e portabilità il Pro. Per confrontare le novità condivise fra i due modelli è disponibile anche la scheda su <a href="https://aivision.altervista.org/iphone-18-pro-recensione-novita/">iPhone 18 Pro e chip A20 Pro</a>.</p>"""
}
}

def plain(s): return " ".join(html.unescape(re.sub(r"<[^>]+>"," ",s or "")).split())
def words(s): return len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ]+(?:['’][\wÀ-ÖØ-öø-ÿ]+)*\b",plain(s)))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("mode",choices=["prepare","apply"]);mode=ap.parse_args().mode
    base=os.getenv("WP_BASE_URL","").rstrip("/").removesuffix("/wp-json");user=os.getenv("WP_USERNAME","");password=os.getenv("WP_APP_PASSWORD","")
    if base!=BASE or not user or not password: raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    s=requests.Session();s.auth=(user,password);s.headers["User-Agent"]="AIVision-Technical-Article-Repair/1.0"
    def read(pid):
        r=s.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=(8,30));r.raise_for_status();return r.json()
    if mode=="prepare":
        changes=[]
        for pid,spec in UPDATES.items():
            p=read(pid)
            if p.get("status")!="publish" or p.get("slug")!=spec["slug"]: raise RuntimeError(f"Post {pid}: stato o slug inatteso.")
            raw=(p.get("content") or {}).get("raw");seo=p.get("aivision_seo")
            if not isinstance(raw,str) or not isinstance(seo,dict) or words(raw)>spec["max_words"]: raise RuntimeError(f"Post {pid}: contenuto/SEO inatteso.")
            for link in re.findall(r'href="(https://aivision\.altervista\.org/[^"]+)"',spec["content"]):
                v=s.get(link,timeout=(8,25),allow_redirects=True)
                if v.status_code!=200 or not v.url.startswith(BASE+"/"): raise RuntimeError("Link interno non valido: "+link)
            after=dict(seo);after.update(spec["seo"])
            changes.append({"id":pid,"slug":spec["slug"],"modified":p.get("modified"),"before_content":raw,"after_content":spec["content"],"before_seo":seo,"after_seo":after,"before_words":words(raw),"after_words":words(spec["content"])})
        payload={"site":BASE,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"changes":changes}
        PLAN.parent.mkdir(parents=True,exist_ok=True);PLAN.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        BACKUP.write_text(json.dumps({"site":BASE,"created_at":payload["created_at"],"posts":[{"id":x["id"],"slug":x["slug"],"modified":x["modified"],"content_raw":x["before_content"],"aivision_seo":x["before_seo"]} for x in changes]},ensure_ascii=False,indent=2),encoding="utf-8")
        for x in changes: print(f"Post {x['id']}: {x['before_words']} -> {x['after_words']} parole.")
        print("Backup pronto; nessuna modifica ancora eseguita.")
        return
    plan=json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("site")!=BASE or len(plan.get("changes",[]))!=4: raise RuntimeError("Piano non valido.")
    results=[]
    for row in plan["changes"]:
        live=read(row["id"]);raw=(live.get("content") or {}).get("raw")
        if live.get("status")!="publish" or live.get("slug")!=row["slug"] or live.get("modified")!=row["modified"] or raw!=row["before_content"] or live.get("aivision_seo")!=row["before_seo"]: raise RuntimeError(f"Post {row['id']} cambiato dopo il backup.")
        r=s.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",params={"context":"edit"},json={"content":row["after_content"],"aivision_seo":row["after_seo"]},timeout=(8,40),allow_redirects=False);r.raise_for_status()
        saved=read(row["id"])
        if (saved.get("content") or {}).get("raw")!=row["after_content"]: raise RuntimeError(f"Contenuto non verificato {row['id']}")
        final=saved.get("aivision_seo") or {}
        for key,value in row["after_seo"].items():
            if final.get(key)!=value: raise RuntimeError(f"SEO {key} non verificato {row['id']}")
        results.append({"id":row["id"],"slug":row["slug"],"status":"updated_and_verified","before_words":row["before_words"],"after_words":row["after_words"],"seo_title":final.get("seo_title"),"seo_description":final.get("seo_description")})
        print(f"Post {row['id']}: aggiornato e verificato.")
    RESULT.write_text(json.dumps({"completed_at":dt.datetime.now(dt.timezone.utc).isoformat(),"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Completati:",len(results))
if __name__=="__main__":main()
