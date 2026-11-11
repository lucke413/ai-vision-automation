#!/usr/bin/env python3
"""Aggiorna quattro articoli brevi o datati, con backup integrale e verifica."""
from __future__ import annotations
import argparse, datetime as dt, html, json, os, re
from pathlib import Path
import requests

BASE="https://aivision.altervista.org"
PLAN=Path("data/date_sensitive_articles_plan.json")
BACKUP=Path("data/date_sensitive_articles_backup.json")
RESULT=Path("data/date_sensitive_articles_result.json")
UPDATES={
461:{
"slug":"eni-tagli-gas-luce-ottobre",
"title":"Eni e Plenitude: sconto 30% su luce e gas, come funzionava",
"seo":{"seo_title":"Eni Plenitude: sconto 30% luce e gas, scadenza e dettagli","seo_description":"L'offerta Eni per l'Italia prevedeva uno sconto del 30% su luce e gas fino al 24 ottobre 2026. Ecco condizioni, risparmio stimato e scadenza.","focus_keyphrase":"Eni Plenitude sconto luce gas"},
"max_words":200,
"content":"""<p>L'iniziativa Eni per l'Italia ha esteso al mercato domestico dell'energia il piano di sostegno già avviato sui carburanti. Attraverso Plenitude, il gruppo aveva proposto uno sconto del 30% sui corrispettivi di luce e gas rispetto alla propria principale offerta a prezzo fisso, con il blocco del prezzo della materia prima per due anni. È importante chiarire che si trattava di una promozione a tempo: la finestra per aderire si è chiusa il 24 ottobre 2026 e, alla data di questo aggiornamento, non va considerata un'offerta ancora sottoscrivibile.</p>
<h2>Quanto si poteva risparmiare</h2>
<p>Secondo i dati comunicati da Eni il 29 settembre 2026, lo sconto era stimato in circa 100 euro all'anno sulla fornitura del gas e in una cifra analoga per l'elettricità. Per chi sceglieva entrambe le utenze, il beneficio indicativo arrivava quindi a circa 200 euro annui. Non si trattava però di un rimborso fisso uguale per tutti: la stima dipendeva dai consumi presi come riferimento e dal confronto con l'offerta standard utilizzata per il calcolo.</p>
<p>Per la componente elettrica, il confronto indicato dall'azienda considerava un'abitazione principale con potenza impegnata di 3 kW e consumi annui di 2.000 kWh. Per il gas veniva utilizzato il profilo di un cliente Plenitude con consumi di 600 Smc all'anno. Il risparmio reale di una famiglia poteva quindi risultare diverso in base a consumi, imposte, oneri e condizioni del contratto.</p>
<h2>Quando era possibile aderire</h2>
<p>L'offerta era prevista dal 1° ottobre e poteva essere sottoscritta tramite Plenitude entro il 24 ottobre 2026. Il prezzo della materia prima veniva mantenuto fisso per 24 mesi, elemento che offriva una maggiore prevedibilità della spesa rispetto a una tariffa variabile. Il blocco riguardava le condizioni economiche definite nell'offerta e non significava che ogni voce della bolletta, comprese imposte e componenti regolate, restasse necessariamente invariata per due anni.</p>
<h2>Cosa controllare prima di scegliere una nuova tariffa</h2>
<p>Chi oggi sta cercando un contratto luce e gas dovrebbe confrontare il costo della materia prima, le quote fisse mensili, la durata delle condizioni economiche, eventuali costi di attivazione e le modalità di rinnovo. È utile utilizzare il Portale Offerte e leggere la scheda sintetica del contratto, senza basarsi soltanto sulla percentuale di sconto pubblicizzata. Una riduzione del 30% rispetto a una tariffa di riferimento non garantisce automaticamente che l'offerta sia la più conveniente sul mercato.</p>
<p>La promozione Eni per l'Italia resta quindi un'iniziativa rilevante per capire come il gruppo abbia cercato di alleggerire la spesa energetica delle famiglie nell'autunno 2026, ma la sua scadenza va tenuta presente. Per valutare una nuova adesione occorre verificare le condizioni commerciali effettivamente disponibili oggi, senza dare per ancora attivo il bonus annunciato a settembre.</p>"""
},
566:{
"slug":"football-manager-27-data-di-uscita-e-versioni",
"title":"Football Manager 27 è disponibile: piattaforme e versioni",
"seo":{"seo_title":"Football Manager 27 è disponibile: piattaforme e versioni","seo_description":"Football Manager 27 è arrivato su PC, Mac, PS5 e Xbox: ecco le versioni Console, Mobile e Touch e le principali novità al lancio.","focus_keyphrase":"Football Manager 27"},
"max_words":200,
"content":"""<p>Football Manager 27 è arrivato sulle piattaforme previste per il lancio e segna il nuovo capitolo della simulazione calcistica sviluppata da Sports Interactive e pubblicata da SEGA. La distribuzione digitale è partita il 10 novembre 2026, con le versioni PC e Mac affiancate dalle edizioni per console e dispositivi mobili. La serie mantiene il suo impianto da gestionale sportivo, ma punta a rendere più fluida la navigazione e più coinvolgente la vita del club anche al di fuori dei novanta minuti.</p>
<h2>Le versioni disponibili</h2>
<p>Su computer, FM27 è disponibile per PC e Mac attraverso Steam, Epic Games Store e l'app Xbox per PC. Il gioco è inoltre incluso nei cataloghi PC Game Pass e Xbox Game Pass Ultimate secondo le condizioni dell'abbonamento. FM27 Console è destinato a PlayStation 5 e Xbox Series X|S, mentre FM27 Mobile viene distribuito attraverso Netflix sui dispositivi compatibili. È prevista anche FM27 Touch tramite Apple Arcade, con disponibilità e funzioni legate alla piattaforma.</p>
<p>Le edizioni non sono semplicemente copie identiche con una diversa icona: interfaccia, controlli e alcune modalità sono adattati al dispositivo. La versione PC offre l'esperienza più completa per chi preferisce gestire ogni dettaglio da mouse e tastiera; Console semplifica l'interazione con il controller; Mobile è pensata per sessioni più rapide su smartphone. Prima di acquistare conviene quindi verificare quale edizione corrisponde al proprio modo di giocare e ai servizi già sottoscritti.</p>
<h2>Le novità principali di FM27</h2>
<p>Sports Interactive ha lavorato sulla navigazione e sull'organizzazione delle informazioni, con l'obiettivo di ridurre i passaggi necessari per raggiungere le schermate più utilizzate. Fra gli elementi messi in evidenza figurano una gestione più chiara dei sorteggi di coppa, una giornata di chiusura del mercato più ricca di aggiornamenti e un flusso di notizie rinnovato per seguire ciò che accade nel mondo calcistico oltre la propria squadra.</p>
<p>Anche l'esperienza della partita è stata rivista per aumentare atmosfera e leggibilità degli incontri. Le modifiche riguardano la presentazione del match e il modo in cui vengono raccontati gli eventi, così da dare più peso ai momenti chiave della stagione. Il gioco continua a ruotare attorno a tattica, mercato, allenamento, gestione dello spogliatoio e rapporto con la dirigenza: le novità puntano a rendere queste attività più accessibili senza eliminare la profondità che caratterizza la serie.</p>
<h2>Accesso anticipato e copie fisiche</h2>
<p>Prima del lancio digitale era prevista una Launch Preview per chi aveva effettuato il preacquisto presso rivenditori digitali SEGA autorizzati. Per le copie fisiche, la versione PC è arrivata il 10 novembre, mentre quella PlayStation 5 è prevista dal 20 novembre 2026. Date e disponibilità possono variare in base al negozio e al mercato.</p>
<h2>Quale versione scegliere</h2>
<p>Chi vuole il massimo controllo e una gestione approfondita dovrebbe orientarsi sulla versione PC o Mac. Console è più adatta a chi gioca dal divano, Mobile a chi preferisce sessioni brevi e Touch a chi utilizza l'ecosistema Apple Arcade. Prima dell'acquisto è consigliabile verificare i requisiti, la presenza del titolo nel proprio abbonamento e le differenze tra le edizioni. In questo modo si evita di pagare due volte per una versione che non offre le funzioni desiderate.</p>"""
},
527:{
"slug":"blender-su-android-tablet-2027",
"title":"Blender su Android: il progetto per tablet è ancora in sviluppo",
"seo":{"seo_title":"Blender su Android: cosa sappiamo del progetto tablet","seo_description":"Blender sta lavorando al supporto Android con priorità ai tablet. Non c'è ancora una data ufficiale di rilascio né un APK pubblico confermato.","focus_keyphrase":"Blender Android tablet"},
"max_words":220,
"content":"""<p>Blender sta lavorando all'estensione del proprio software di grafica 3D ai dispositivi Android, con un progetto che guarda soprattutto ai tablet. L'obiettivo è portare una parte dell'esperienza desktop su hardware mobile, ma non si tratta ancora di un'app pronta per il pubblico. Gli aggiornamenti pubblici del progetto indicano che il supporto iniziale alla piattaforma è in fase di sviluppo e che il lavoro si sta concentrando su Android; iOS è indicato come possibilità in valutazione, non come piattaforma già confermata.</p>
<h2>Perché partire dai tablet</h2>
<p>Blender è un ambiente complesso, utilizzato per modellazione, animazione, rendering, compositing e altre attività di produzione 3D. Trasferire l'interfaccia su uno schermo touch non significa semplicemente ridurre le dimensioni dei pulsanti. Molti strumenti sono progettati per mouse, tastiera e scorciatoie, mentre su un tablet servono controlli più adatti alle dita e, dove disponibile, alla penna digitale.</p>
<p>Per questo il lavoro richiede più passaggi. Il team deve prima verificare che l'applicazione possa funzionare sui dispositivi Android supportati, poi migliorare l'interazione touch e affrontare la gestione dei file. Un punto centrale è la possibilità di scambiare progetti con la versione desktop, così da non creare un ambiente isolato: l'utente dovrebbe poter iniziare o modificare un lavoro sul tablet e continuarlo su un computer, mantenendo compatibilità e organizzazione dei file.</p>
<h2>Interfaccia touch e flusso di lavoro</h2>
<p>La sfida più importante riguarda l'esperienza d'uso. Modellare un oggetto, selezionare vertici, spostare elementi nella scena e modificare parametri richiede precisione. Una versione mobile dovrà quindi trovare un equilibrio tra comandi rapidi, pannelli leggibili e strumenti avanzati. Il supporto a una penna può essere utile per alcune operazioni, ma non sostituisce la necessità di ripensare i menu e la navigazione per un display touch.</p>
<p>Il progetto comprende anche il lavoro sugli strumenti di compilazione e debug, indispensabili per permettere agli sviluppatori di creare e distribuire versioni Android in modo affidabile. È un'attività meno visibile rispetto alle funzioni dell'interfaccia, ma fondamentale per poter aggiornare l'app e correggere problemi sui diversi dispositivi.</p>
<h2>Quando arriverà Blender per Android?</h2>
<p>Al momento non c'è una data pubblica definitiva che consenta di promettere il rilascio nella prima metà del 2027. La roadmap tecnica descrive attività ancora in corso e non equivale a un calendario commerciale. Anche la disponibilità di un APK scaricabile non va data per scontata: prima di installare pacchetti trovati su siti non ufficiali è meglio verificare che provengano direttamente dal progetto Blender.</p>
<h2>Cosa aspettarsi</h2>
<p>La prospettiva più concreta è una prima versione focalizzata sul funzionamento di Blender su tablet Android, seguita da miglioramenti progressivi all'interfaccia e all'integrazione con il desktop. Per chi lavora già con il software, il vantaggio potenziale è poter consultare o modificare progetti lontano dalla postazione principale. Fino a quando il team non pubblicherà requisiti, dispositivi supportati e una data ufficiale, ogni previsione più precisa deve essere considerata provvisoria.</p>"""
},
533:{
"slug":"tv-lg-nanocell-ai-75-offerta-amazon",
"title":"LG NanoCell AI 75 pollici: caratteristiche e offerta Amazon di ottobre",
"seo":{"seo_title":"LG NanoCell AI 75 pollici: caratteristiche e prezzo di ottobre","seo_description":"LG NanoCell AI da 75 pollici: pannello 4K a 60 Hz, processore α7 Gen8 e webOS 25. Il prezzo di 569 euro era riferito all'offerta del 6-7 ottobre 2026.","focus_keyphrase":"LG NanoCell AI 75 pollici"},
"max_words":350,
"content":"""<p>Il televisore LG NanoCell AI da 75 pollici della gamma NANO80 2025 è stato protagonista di una promozione Amazon durante la Festa delle Offerte Prime del 6 e 7 ottobre 2026. In quell'occasione il prezzo segnalato era di 569 euro, rispetto a un riferimento precedente di circa 651,38 euro. Si tratta di un dato storico legato a quella specifica finestra promozionale: non è una quotazione attuale garantita e disponibilità, prezzo e venditore possono essere cambiati dopo l'evento.</p>
<h2>Schermo 4K e tecnologia NanoCell</h2>
<p>Il modello appartiene alla famiglia NanoCell 2025 e utilizza un pannello LCD con risoluzione 4K Ultra HD, pari a 3.840 x 2.160 pixel. La tecnologia NanoCell è progettata per migliorare la resa dei colori filtrando alcune componenti indesiderate della luce, mentre il processore α7 4K Gen8 con intelligenza artificiale gestisce l'elaborazione delle immagini e l'upscaling dei contenuti a risoluzione inferiore. La qualità finale dipende comunque dalla sorgente: un video in bassa definizione non diventa nativamente 4K solo perché viene elaborato dal televisore.</p>
<p>Fra le funzioni video sono indicati HDR10 e HLG, Dynamic Tone Mapping e FILMMAKER MODE. Quest'ultima cerca di rispettare le impostazioni visive scelte dal regista, riducendo alcune elaborazioni automatiche. È una dotazione adatta alla visione di film, serie e contenuti in streaming, ma chi cerca il massimo supporto ai formati HDR deve controllare attentamente la scheda del modello: la gamma NANO80 non va confusa con le linee OLED o con le serie LG di fascia superiore.</p>
<h2>Gaming: bene le funzioni di base, limite a 60 Hz</h2>
<p>Per i videogiochi sono presenti Game Optimizer, ALLM, HGiG e VRR fino a 60 Hz. Sono caratteristiche utili per collegare console e ridurre la latenza, ma il pannello è nativamente a 50/60 Hz: non è un televisore pensato per sfruttare i 120 Hz delle console di ultima generazione. Chi gioca soprattutto a titoli competitivi o desidera frequenze più elevate dovrebbe valutare una fascia superiore prima dell'acquisto.</p>
<h2>Audio, sistema smart e connessioni</h2>
<p>La sezione audio utilizza un sistema stereo 2.0 da 20 W, con elaborazione AI Sound Pro. Per un salotto ampio o per ottenere bassi più presenti può essere utile affiancare una soundbar. Il sistema operativo webOS 25 integra le principali applicazioni smart e le funzioni di ricerca e controllo vocale basate sull'AI. La dotazione comprende inoltre connessioni HDMI con eARC e ALLM, USB, Wi-Fi e Bluetooth; il numero e le caratteristiche degli ingressi vanno verificati sulla scheda del codice modello esatto.</p>
<h2>Il prezzo di 569 euro era conveniente?</h2>
<p>Durante la promozione di ottobre, 569 euro rappresentavano un prezzo interessante per un televisore da 75 pollici con risoluzione 4K e funzioni smart aggiornate. Il compromesso principale era la frequenza di aggiornamento a 60 Hz e l'assenza delle caratteristiche tipiche dei modelli premium, come un pannello OLED o un sistema di local dimming avanzato. Per un uso misto con film, streaming e televisione tradizionale può essere una scelta equilibrata, mentre per gaming ad alte prestazioni conviene confrontarlo con modelli a 120 Hz.</p>
<p>Prima di acquistarlo oggi è necessario verificare il prezzo corrente, il codice modello completo, chi vende e spedisce il prodotto, la politica di reso e la garanzia. Il valore di 569 euro citato in questo articolo si riferisce alla promozione Amazon del 6-7 ottobre 2026 e non deve essere interpretato come un'offerta ancora attiva.</p>"""
}
}

def plain(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())
def words(s):
    return len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ]+(?:['’][\wÀ-ÖØ-öø-ÿ]+)*\b",plain(s)))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("mode",choices=["prepare","apply"]);mode=ap.parse_args().mode
    base=os.getenv("WP_BASE_URL","").rstrip("/").removesuffix("/wp-json");user=os.getenv("WP_USERNAME","");password=os.getenv("WP_APP_PASSWORD","")
    if base!=BASE or not user or not password: raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    s=requests.Session();s.auth=(user,password);s.headers["User-Agent"]="AIVision-Date-Sensitive-Article-Repair/1.0"
    def read(pid):
        r=s.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=(8,30));r.raise_for_status();return r.json()
    if mode=="prepare":
        changes=[]
        for pid,spec in UPDATES.items():
            p=read(pid)
            if p.get("status")!="publish" or p.get("slug")!=spec["slug"]: raise RuntimeError(f"Post {pid}: stato o slug inatteso.")
            raw=(p.get("content") or {}).get("raw");seo=p.get("aivision_seo")
            if not isinstance(raw,str) or not isinstance(seo,dict) or words(raw)>spec["max_words"]: raise RuntimeError(f"Post {pid}: contenuto o SEO inatteso, stop.")
            for link in re.findall(r'href="(https://aivision\.altervista\.org/[^"]+)"',spec["content"]):
                v=s.get(link,timeout=(8,25),allow_redirects=True)
                if v.status_code!=200 or not v.url.startswith(BASE+"/"): raise RuntimeError("Link interno non valido: "+link)
            after=dict(seo);after.update(spec["seo"])
            changes.append({"id":pid,"slug":spec["slug"],"modified":p.get("modified"),"before_content":raw,"after_content":spec["content"],"before_seo":seo,"after_seo":after,"before_words":words(raw),"after_words":words(spec["content"])})
        payload={"site":BASE,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"changes":changes}
        PLAN.parent.mkdir(parents=True,exist_ok=True);PLAN.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        BACKUP.write_text(json.dumps({"site":BASE,"created_at":payload["created_at"],"posts":[{"id":x["id"],"slug":x["slug"],"modified":x["modified"],"content_raw":x["before_content"],"aivision_seo":x["before_seo"]} for x in changes]},ensure_ascii=False,indent=2),encoding="utf-8")
        for x in changes: print(f"Post {x['id']}: {x['before_words']} -> {x['after_words']} parole.")
        print("Piano e backup creati.")
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
