#!/usr/bin/env python3
"""Espande quattro notizie brevi con dati verificati e backup preventivo."""
from __future__ import annotations
import argparse, datetime as dt, html, json, os, re
from pathlib import Path
import requests

BASE="https://aivision.altervista.org"
PLAN=Path("data/next_short_articles_plan.json")
BACKUP=Path("data/next_short_articles_backup.json")
RESULT=Path("data/next_short_articles_result.json")
UPDATES={
425:{
"slug":"the-witcher-3-wild-hunt-remastered-disponibile-oggi",
"title":"The Witcher 3 Remastered è disponibile: upgrade gratuito e novità",
"seo":{"seo_title":"The Witcher 3 Remastered: upgrade gratis e novità","seo_description":"The Witcher 3 Remastered è disponibile dal 29 settembre: upgrade gratuito, miglioramenti grafici e gameplay, piattaforme e salvataggi compatibili.","focus_keyphrase":"The Witcher 3 Remastered"},
"max_words":200,
"content":"""<p><em>The Witcher 3: Wild Hunt – Remastered</em> è disponibile dal 29 settembre 2026 e porta una versione aggiornata del gioco di ruolo di CD Projekt RED sulle piattaforme di attuale generazione. La notizia più importante per chi possiede già il titolo è il costo dell'aggiornamento: l'edizione rimasterizzata viene distribuita gratuitamente agli utenti idonei, senza dover acquistare una seconda copia. L'intervento non si limita a un aumento della risoluzione, ma comprende modifiche alla resa visiva, alle prestazioni e ad alcuni elementi del gameplay.</p>
<h2>Upgrade gratuito: chi può scaricarlo</h2>
<p>L'aggiornamento è previsto per PC, PlayStation 5, Xbox Series X|S e Nintendo Switch 2. Su PC è disponibile attraverso gli ecosistemi digitali supportati, tra cui Steam, GOG, Epic Games Store e Battle.net; su console il passaggio dipende dalla versione già posseduta e dallo store della piattaforma. Chi ha acquistato <em>The Witcher 3</em> su Nintendo Switch originale può richiedere la versione per Switch 2 senza un nuovo acquisto, secondo le condizioni comunicate dallo sviluppatore.</p>
<p>La regola pratica è verificare di utilizzare lo stesso ecosistema nel quale è stato comprato il gioco e controllare la pagina della propria libreria: l'upgrade viene associato alla licenza esistente. La disponibilità e la procedura possono variare leggermente fra piattaforme e regioni, quindi è preferibile controllare lo store prima di avviare un nuovo acquisto.</p>
<h2>Grafica, prestazioni e modifiche al gameplay</h2>
<p>La versione Remastered aggiorna texture, modelli, illuminazione, ombre e vegetazione, con l'obiettivo di rendere più leggibili ambienti, personaggi e mostri. Su PC sono previste opzioni grafiche avanzate, compreso il path tracing sui sistemi compatibili; su PlayStation 5 Pro è indicato un supporto dedicato. La versione nativa per Nintendo Switch 2 sfrutta invece le caratteristiche della nuova console rispetto alla precedente edizione per Switch.</p>
<p>Gli interventi toccano anche il combattimento, le animazioni e il sistema di progressione. Il sistema delle abilità è stato rielaborato e questo comporta un dettaglio da conoscere prima di riprendere una partita: i salvataggi esistenti restano compatibili, ma le abilità vengono azzerate per consentire di distribuire nuovamente i punti secondo le nuove regole. È quindi opportuno controllare la schermata del personaggio prima di affrontare missioni impegnative.</p>
<h2>Le espansioni sono comprese</h2>
<p>Un altro elemento rilevante riguarda <em>Hearts of Stone</em> e <em>Blood and Wine</em>. CD Projekt RED ha comunicato che entrambe sono incluse nell'edizione Remastered e vengono rese disponibili anche a chi possedeva soltanto il gioco base, secondo le condizioni previste per la piattaforma. Questo rende l'aggiornamento particolarmente interessante per chi aveva rimandato l'acquisto dei contenuti aggiuntivi.</p>
<h2>Conviene tornare a giocare?</h2>
<p>Per chi ha già completato l'avventura, il valore dell'aggiornamento dipende soprattutto dalla piattaforma utilizzata e dall'interesse per le migliorie grafiche e di gameplay. Per chi non ha mai giocato a <em>The Witcher 3</em>, la Remastered riunisce il gioco e le due espansioni in un pacchetto più attuale. Prima di scaricare, conviene liberare spazio su disco, verificare la versione corretta e conservare una copia dei salvataggi. Chi segue anche le novità dei giochi in arrivo può leggere l'approfondimento su <a href="https://aivision.altervista.org/gta-6-sondaggio-record-previsioni-vendita/">GTA 6 e le aspettative di vendita</a>.</p>"""
},
431:{
"slug":"disponibile-ios-27-0-1-correzioni-novita",
"title":"iOS 27.0.1: le tre correzioni per Face ID, fotocamera e touchscreen",
"seo":{"seo_title":"iOS 27.0.1: corretti Face ID, fotocamera e touch","seo_description":"iOS 27.0.1 risolve riavvii legati a Face ID su iPhone 18 Pro, artefatti nelle foto 2x e blocchi del touchscreen.","focus_keyphrase":"iOS 27.0.1"},
"max_words":200,
"content":"""<p>Apple ha distribuito iOS 27.0.1, un aggiornamento di manutenzione che interviene su tre problemi specifici segnalati sugli iPhone. Non introduce una nuova generazione di funzioni: l'obiettivo è correggere comportamenti anomali comparsi dopo il rilascio di iOS 27, con particolare attenzione ai modelli iPhone 18 Pro e Pro Max, alla fotocamera e alla risposta del touchscreen.</p>
<h2>Il problema di Face ID su iPhone 18 Pro</h2>
<p>La prima correzione riguarda alcuni casi in cui iPhone 18 Pro e iPhone 18 Pro Max potevano riavviarsi inaspettatamente quando Face ID non riusciva a completare l'autenticazione. Si tratta di un comportamento diverso da un semplice errore di riconoscimento: il problema descritto nelle note di rilascio poteva portare al riavvio del dispositivo. L'aggiornamento è quindi particolarmente rilevante per chi ha riscontrato blocchi o riavvii durante lo sblocco e la verifica dell'identità.</p>
<h2>Correzioni per le foto scattate con zoom 2x</h2>
<p>Il secondo intervento riguarda un artefatto cromatico che poteva comparire in alcune fotografie realizzate con ingrandimento 2x, in determinate condizioni di illuminazione e con apertura f/1,48. Apple specifica che il difetto interessava un numero limitato di dispositivi iPhone 18 Pro e Pro Max. Non significa che tutte le foto scattate con lo zoom 2x fossero coinvolte: il problema era circoscritto a una combinazione precisa di condizioni di scatto e hardware.</p>
<h2>Touchscreen e Centro di Controllo</h2>
<p>La terza correzione risolve un caso in cui l'apertura contemporanea del Centro Notifiche e del Centro di Controllo poteva rendere temporaneamente insensibile il touchscreen. Per chi utilizza spesso i controlli rapidi, il difetto poteva interrompere un gesto quotidiano e richiedere di attendere il ripristino della risposta del display.</p>
<h2>Come installare iOS 27.0.1</h2>
<p>Per verificare la disponibilità dell'aggiornamento basta aprire Impostazioni, entrare in Generali e selezionare Aggiornamento software. Prima di procedere è consigliabile collegare l'iPhone al Wi-Fi, avere una carica sufficiente o collegarlo all'alimentazione e controllare che il backup sia aggiornato. Se l'update non compare subito, si può riprovare più tardi: la distribuzione può essere graduale e dipendere dal dispositivo.</p>
<p>Le note ufficiali descrivono queste correzioni, ma non indicano che iOS 27.0.1 introduca nuove funzioni o un cambiamento generale delle prestazioni. Per chi possiede uno dei modelli interessati, installarlo è il modo più diretto per ricevere i fix. Per conoscere le novità hardware della generazione attuale è disponibile anche la panoramica su <a href="https://aivision.altervista.org/iphone-18-pro-recensione-novita/">iPhone 18 Pro e chip A20 Pro</a>.</p>"""
},
467:{
"slug":"xbox-disc-to-digital-disponibile-per-tutti-gli-utenti",
"title":"Xbox Disc to Digital per tutti: come trasformare i giochi su disco",
"seo":{"seo_title":"Xbox Disc to Digital: come funziona e giochi compatibili","seo_description":"Xbox Disc to Digital è disponibile a tutti dal 29 settembre: come riscattare la licenza digitale e quali limiti controllare.","focus_keyphrase":"Xbox Disc to Digital"},
"max_words":200,
"content":"""<p>La funzione Xbox Disc to Digital è stata estesa a tutti gli utenti delle console compatibili il 29 settembre 2026, dopo una prima fase di test riservata agli iscritti al programma Xbox Insider. L'iniziativa permette di associare una licenza digitale a determinati giochi acquistati su disco, offrendo nuove possibilità di accesso all'interno dell'ecosistema Xbox. Non si tratta però di una conversione automatica di ogni titolo fisico: la compatibilità dipende dal singolo gioco e dagli accordi con il relativo editore.</p>
<h2>Come funziona la procedura</h2>
<p>Per iniziare serve una console dotata di lettore, come Xbox One o Xbox Series X. Si inserisce il disco di un gioco supportato, si avvia il titolo e si controlla se compare l'opzione per richiedere la licenza digitale. Quando la procedura è disponibile, la console associa al gioco l'entitlement digitale previsto dal programma. La disponibilità può essere diversa da un titolo all'altro e l'elenco dei giochi compatibili può ampliarsi nel tempo.</p>
<p>Microsoft ha spiegato che la funzione riguarda la maggior parte dei giochi su disco Xbox One e Xbox Series X, ma non ha promesso la compatibilità universale. Per questo, prima di acquistare un gioco usato pensando di convertirlo, è prudente verificare che quel titolo sia effettivamente supportato. Il disco fisico continua a funzionare come prima e resta importante conservarlo: non va considerato un oggetto da buttare dopo la procedura.</p>
<h2>Quali vantaggi offre la licenza digitale</h2>
<p>Il vantaggio è poter sfruttare alcune caratteristiche della distribuzione digitale quando sono supportate dal gioco. Fra gli esempi citati da Xbox rientrano Play Anywhere e Xbox Cloud Gaming: se il titolo partecipa ai rispettivi programmi, la licenza può consentire di giocare anche su dispositivi compatibili o tramite streaming. La disponibilità di queste opzioni non è automatica per tutti i giochi e dipende dalle condizioni del singolo prodotto.</p>
<p>La funzione può risultare utile anche a chi possiede una collezione fisica e vuole sfruttare meglio l'ecosistema digitale, ma non sostituisce la verifica della compatibilità. Una copia su disco non garantisce da sola l'accesso alla versione digitale di qualsiasi gioco, né rende trasferibili tutte le licenze a piacimento.</p>
<h2>Cosa fare se l'opzione non compare</h2>
<p>Se la console non mostra la possibilità di riscattare la licenza, conviene prima riavviarla e controllare che il software di sistema sia aggiornato. È utile anche provare un altro titolo noto come compatibile e verificare di aver inserito il disco nella console con lettore. Se l'opzione manca ancora, il gioco potrebbe non essere incluso nel programma oppure la distribuzione della funzione potrebbe non essere ancora arrivata a quella console.</p>
<h2>Una novità utile per la conservazione dei giochi</h2>
<p>Disc to Digital prova a ridurre la distanza fra collezione fisica e servizi digitali, senza eliminare il supporto originale. Per chi acquista giochi usati o conserva titoli fuori catalogo, il punto decisivo resta la lista di compatibilità, che non è fissa. Per altre notizie sul mercato videoludico è possibile leggere anche l'analisi su <a href="https://aivision.altervista.org/zelda-ocarina-of-time-remake-code-negozi-fisico/">Zelda e il ritorno delle copie fisiche nei negozi</a>.</p>"""
},
486:{
"slug":"safari-funzione-avvisami-monitorare-prezzi",
"title":"Safari Avvisami: come monitorare prezzi e modifiche alle pagine",
"seo":{"seo_title":"Safari Avvisami: monitorare prezzi e pagine web","seo_description":"Con Safari su iOS 27, Avvisami controlla le modifiche alle pagine e segnala variazioni di prezzo o disponibilità tramite notifiche.","focus_keyphrase":"Safari Avvisami"},
"max_words":200,
"content":"""<p>Con iOS 27 Safari introduce Avvisami, una funzione pensata per seguire nel tempo le modifiche di una pagina web senza doverla riaprire manualmente ogni giorno. Può essere utile soprattutto quando si sta aspettando un ribasso di prezzo, il ritorno in disponibilità di un prodotto o un aggiornamento su una pagina che cambia spesso. La funzione utilizza Apple Intelligence sui dispositivi compatibili e invia una notifica quando rileva un cambiamento corrispondente a ciò che l'utente ha chiesto di monitorare.</p>
<h2>Come si attiva Avvisami in Safari</h2>
<p>La procedura parte dalla pagina che si vuole controllare. Su iPhone si apre Safari, si visita il sito interessato e si tocca il menu della pagina nella barra degli strumenti. Da qui si seleziona Avvisami e si descrive che cosa si desidera tenere d'occhio, per esempio una variazione del prezzo o la disponibilità di un articolo. Se l'interfaccia lo consente, si può entrare nelle opzioni di modifica per regolare la frequenza dei controlli; al termine si conferma la configurazione.</p>
<p>Quando Safari rileva un aggiornamento pertinente, mostra una notifica sul dispositivo. In questo modo non è necessario lasciare decine di schede aperte o controllare ripetutamente lo stesso indirizzo. La funzione è utile anche per pagine informative, purché la modifica da rilevare sia riconoscibile dal sistema.</p>
<h2>Perché può essere utile per gli acquisti online</h2>
<p>Un esempio pratico è il monitoraggio di un prodotto che non si vuole acquistare al prezzo attuale. Si apre la pagina del negozio, si imposta Avvisami per controllare il prezzo o la disponibilità e si attende la notifica. Questo non equivale a un comparatore prezzi: Safari non garantisce di trovare il prezzo più basso fra più negozi e non sostituisce il controllo delle condizioni di vendita, dei costi di spedizione o dell'affidabilità del rivenditore. Serve piuttosto a seguire una singola pagina nel tempo.</p>
<p>La stessa logica può essere applicata a pagine di notizie, calendari o servizi che pubblicano aggiornamenti. Il vantaggio è ridurre i controlli manuali; il limite è che il sistema deve riuscire a riconoscere il tipo di cambiamento richiesto e il sito deve presentare le informazioni in modo leggibile.</p>
<h2>Compatibilità e requisiti</h2>
<p>Avvisami è legata alle funzioni di Apple Intelligence e richiede iOS 27 o versioni successive su un iPhone compatibile. Apple indica il supporto per iPhone 15 Pro, iPhone 15 Pro Max e i modelli iPhone 16 o successivi abilitati ad Apple Intelligence. La disponibilità può variare in base alla lingua, alla regione e al dispositivo; possono inoltre essere previsti limiti di utilizzo. Se la voce Avvisami non compare nel menu di Safari, è opportuno verificare la compatibilità del modello, la versione del sistema e le impostazioni di Apple Intelligence.</p>
<h2>Una funzione da usare con aspettative realistiche</h2>
<p>Avvisami è uno strumento di monitoraggio comodo per una pagina specifica, non un servizio che confronta automaticamente tutti i negozi o garantisce notifiche istantanee. Per offerte importanti conviene continuare a verificare prezzo finale, disponibilità e condizioni direttamente sul sito del venditore. Chi vuole seguire anche le novità hardware Apple può approfondire <a href="https://aivision.altervista.org/iphone-18-pro-recensione-novita/">le caratteristiche di iPhone 18 Pro</a>.</p>"""
}
}

def plain(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())
def words(s):
    return len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ]+(?:['’][\wÀ-ÖØ-öø-ÿ]+)*\b",plain(s)))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("mode",choices=["prepare","apply"])
    mode=ap.parse_args().mode
    base=os.getenv("WP_BASE_URL","").rstrip("/").removesuffix("/wp-json")
    user=os.getenv("WP_USERNAME",""); password=os.getenv("WP_APP_PASSWORD","")
    if base!=BASE or not user or not password: raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    s=requests.Session(); s.auth=(user,password); s.headers["User-Agent"]="AIVision-Next-Short-Article-Repair/1.0"
    def read(pid):
        r=s.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=(8,30)); r.raise_for_status(); return r.json()
    if mode=="prepare":
        changes=[]
        for pid,spec in UPDATES.items():
            p=read(pid)
            if p.get("status")!="publish" or p.get("slug")!=spec["slug"]: raise RuntimeError(f"Post {pid}: stato o slug inatteso.")
            raw=(p.get("content") or {}).get("raw"); seo=p.get("aivision_seo")
            if not isinstance(raw,str) or not isinstance(seo,dict): raise RuntimeError(f"Post {pid}: contenuto o SEO non accessibile.")
            if words(raw)>spec["max_words"]: raise RuntimeError(f"Post {pid}: testo già cambiato, stop.")
            for link in re.findall(r'href="(https://aivision\.altervista\.org/[^"]+)"',spec["content"]):
                v=s.get(link,timeout=(8,25),allow_redirects=True)
                if v.status_code!=200 or not v.url.startswith(BASE+"/"): raise RuntimeError("Link interno non valido: "+link)
            after_seo=dict(seo); after_seo.update(spec["seo"])
            changes.append({"id":pid,"slug":spec["slug"],"modified":p.get("modified"),
                "before_content":raw,"after_content":spec["content"],"before_seo":seo,"after_seo":after_seo,
                "before_words":words(raw),"after_words":words(spec["content"])})
        payload={"site":BASE,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"changes":changes}
        PLAN.parent.mkdir(parents=True,exist_ok=True)
        PLAN.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        BACKUP.write_text(json.dumps({"site":BASE,"created_at":payload["created_at"],
            "posts":[{"id":x["id"],"slug":x["slug"],"modified":x["modified"],"content_raw":x["before_content"],"aivision_seo":x["before_seo"]} for x in changes]},
            ensure_ascii=False,indent=2),encoding="utf-8")
        for x in changes: print(f"Post {x['id']}: {x['before_words']} -> {x['after_words']} parole.")
        print("Piano e backup creati; nessuna scrittura ancora eseguita.")
        return
    plan=json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("site")!=BASE or len(plan.get("changes",[]))!=4: raise RuntimeError("Piano non valido.")
    results=[]
    for row in plan["changes"]:
        live=read(row["id"]); raw=(live.get("content") or {}).get("raw")
        if live.get("status")!="publish" or live.get("slug")!=row["slug"] or live.get("modified")!=row["modified"] or raw!=row["before_content"] or live.get("aivision_seo")!=row["before_seo"]:
            raise RuntimeError(f"Post {row['id']} cambiato dopo il backup; stop.")
        r=s.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",params={"context":"edit"},
            json={"content":row["after_content"],"aivision_seo":row["after_seo"]},timeout=(8,40),allow_redirects=False); r.raise_for_status()
        saved=read(row["id"])
        if (saved.get("content") or {}).get("raw")!=row["after_content"]: raise RuntimeError(f"Contenuto non verificato: {row['id']}")
        final=saved.get("aivision_seo") or {}
        for key,value in row["after_seo"].items():
            if final.get(key)!=value: raise RuntimeError(f"SEO {key} non verificato: {row['id']}")
        results.append({"id":row["id"],"slug":row["slug"],"status":"updated_and_verified","before_words":row["before_words"],"after_words":row["after_words"],"seo_title":final.get("seo_title"),"seo_description":final.get("seo_description")})
        print(f"Post {row['id']}: aggiornato e verificato.")
    RESULT.write_text(json.dumps({"completed_at":dt.datetime.now(dt.timezone.utc).isoformat(),"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Completati:",len(results))

if __name__=="__main__": main()
