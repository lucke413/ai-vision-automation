#!/usr/bin/env python3
"""Aggiorna quattro articoli commerciali e di calendario, distinguendo prezzi storici e attuali."""
from __future__ import annotations
import argparse, datetime as dt, html, json, os, re
from pathlib import Path
import requests
BASE="https://aivision.altervista.org"
PLAN=Path("data/commerce_calendar_articles_plan.json")
BACKUP=Path("data/commerce_calendar_articles_backup.json")
RESULT=Path("data/commerce_calendar_articles_result.json")
UPDATES={
602:{
"slug":"samsung-galaxy-watch8-offerta-amazon",
"title":"Samsung Galaxy Watch8: caratteristiche e prezzo dell'offerta di ottobre",
"seo":{"seo_title":"Samsung Galaxy Watch8: funzioni e prezzo di ottobre","seo_description":"Galaxy Watch8 40 mm: display AMOLED, Exynos W1000 e funzioni salute. I 229 euro erano il prezzo Amazon osservato nella promozione di ottobre 2026.","focus_keyphrase":"Samsung Galaxy Watch8"},
"max_words":320,
"content":"""<p>Samsung Galaxy Watch8 nella versione Bluetooth da 40 mm è stato proposto su Amazon a 229 euro durante una promozione di ottobre 2026, contro il prezzo di listino indicato nell'articolo di 329 euro. Il prezzo di 229 euro è una rilevazione storica della campagna promozionale e non va considerato una quotazione attuale: offerte, disponibilità e venditore possono cambiare. La versione citata è quella Dark Gray da 40 mm, più compatta rispetto al modello da 44 mm e pensata per chi preferisce uno smartwatch leggero.</p>
<h2>Display, processore e autonomia</h2>
<p>Il Galaxy Watch8 da 40 mm utilizza un display Super AMOLED da 1,34 pollici con risoluzione di 438 x 438 pixel e modalità Always On. La cassa misura 40,4 x 42,7 x 8,6 millimetri e pesa circa 30 grammi senza cinturino. Al suo interno lavora il processore Exynos W1000 a cinque core, realizzato con processo a 3 nanometri, affiancato da 2 GB di RAM e 32 GB di memoria. Il sistema operativo è Wear OS 6 con interfaccia One UI 8 Watch.</p>
<p>La batteria del modello da 40 mm ha una capacità tipica di 325 mAh. Samsung dichiara fino a 30 ore con Always On Display attivo, ma il risultato reale dipende da GPS, notifiche, luminosità, chiamate e monitoraggio continuo. Chi utilizza spesso il GPS per allenarsi o tiene molte funzioni attive dovrebbe mettere in conto ricariche frequenti. La certificazione 5 ATM, IP68 e MIL-STD-810H aggiunge protezione per l'uso quotidiano, senza rendere l'orologio indistruttibile.</p>
<h2>Salute, sonno e allenamento</h2>
<p>Il sensore BioActive combina rilevazione ottica della frequenza cardiaca, segnale elettrico cardiaco e analisi dell'impedenza bioelettrica. Sono presenti strumenti per monitorare il sonno, il carico vascolare, l'indice antiossidante, la composizione corporea e alcune metriche cardiache. Energy Score sintetizza informazioni raccolte durante il riposo e l'attività per offrire un'indicazione generale della preparazione della giornata. La funzione di coaching per la corsa propone programmi personalizzati in base al livello dell'utente.</p>
<p>Queste misurazioni sono strumenti di benessere e non sostituiscono esami o valutazioni mediche. La disponibilità di ECG, pressione arteriosa e altre funzioni può dipendere dal Paese, dallo smartphone abbinato e dalle autorizzazioni richieste. Prima dell'acquisto è quindi opportuno verificare quali funzioni siano effettivamente attive sul proprio telefono.</p>
<h2>Bluetooth o LTE: quale versione scegliere</h2>
<p>La versione Bluetooth richiede la vicinanza dello smartphone per alcune funzioni di connettività, mentre la variante LTE può gestire chiamate e dati mobili in modo più indipendente, con un piano compatibile. La versione da 40 mm è più leggera, ma ha una batteria più piccola rispetto al modello da 44 mm. Chi vuole soprattutto notifiche, sonno e allenamenti può preferire il formato compatto; chi desidera più autonomia e un display più grande dovrebbe valutare il 44 mm.</p>
<h2>Il prezzo di 229 euro era interessante?</h2>
<p>Nel periodo promozionale di ottobre 2026, il prezzo di 229 euro rappresentava uno sconto di 100 euro rispetto al riferimento di 329 euro indicato per la versione Bluetooth da 40 mm. Per valutare un acquisto oggi bisogna però controllare il prezzo corrente, la variante esatta, chi vende e spedisce il prodotto e la politica di reso. Non conviene basare la decisione su una promozione terminata: il valore reale dipende dal prezzo effettivamente disponibile al momento dell'ordine.</p>"""
},
599:{
"slug":"giochi-in-uscita-ottobre-offerte",
"title":"Giochi usciti a ottobre 2026: le principali novità per PC e console",
"seo":{"seo_title":"Giochi usciti a ottobre 2026: date e piattaforme","seo_description":"Da Gears of War: E-Day a Phantom Blade Zero: i principali giochi arrivati a ottobre 2026 su PC, PS5, Xbox e Switch 2.","focus_keyphrase":"giochi usciti ottobre 2026"},
"max_words":250,
"content":"""<p>Ottobre 2026 è stato uno dei mesi più densi dell'anno per il calendario videoludico, con uscite distribuite fra PC, PlayStation 5, Xbox Series X|S e Nintendo Switch 2. Il mese ha alternato remaster, nuovi capitoli di serie conosciute, giochi d'azione e produzioni indipendenti. A novembre il calendario di ottobre è ormai concluso: questa pagina diventa quindi un riepilogo delle principali uscite del mese, non una lista di preordini ancora da effettuare.</p>
<h2>Le uscite di inizio ottobre</h2>
<p>Il 1° ottobre sono arrivati <em>Dynasty Warriors 3: Complete Edition Remastered</em> e <em>End of Abyss</em>, insieme ad altre riedizioni e nuove produzioni. Il 2 ottobre è stata la volta di <em>Ace Combat 8: Wings of Theve</em>, nuovo capitolo della serie di combattimento aereo. Il 6 ottobre ha concentrato due nomi di grande richiamo: <em>Gears of War: E-Day</em>, destinato a Xbox e PC, e <em>Star Wars: Galactic Racer</em>, previsto anche su PlayStation 5.</p>
<h2>Metà mese: simulazione, azione e avventura</h2>
<p>Il 13 ottobre è arrivato <em>Planet Zoo 2</em>, che porta la gestione di parchi zoologici su PC e console. Il 15 ottobre ha visto il debutto di <em>Castlevania: Belmont's Curse</em> e di altre produzioni, mentre il 22 ottobre sono arrivati <em>Final Fantasy Resonance</em> e <em>Nintendo Switch Sports Resort</em> per Switch 2. Queste uscite hanno coperto generi molto diversi, dai giochi di ruolo all'azione e alle esperienze sportive pensate per il gioco in compagnia.</p>
<h2>Il finale del mese</h2>
<p>Il 23 ottobre è arrivato <em>Call of Duty: Modern Warfare 4</em>, pubblicato su PC e console compatibili. Il 29 ottobre ha chiuso il mese con <em>Phantom Blade Zero</em> e <em>The Wolf Among Us Remastered</em>, due titoli molto diversi per stile e impostazione. Per chi preferisce i giochi gestionali, il mese successivo ha portato anche <a href="https://aivision.altervista.org/football-manager-27-data-di-uscita-e-versioni/">Football Manager 27</a>, disponibile dal 10 novembre.</p>
<h2>Come scegliere cosa recuperare</h2>
<p>Chi deve ancora recuperare un titolo di ottobre dovrebbe partire dalla piattaforma posseduta e verificare se la versione acquistata include contenuti aggiuntivi o bonus legati a un'edizione specifica. Le date possono differire fra distribuzione digitale e copie fisiche, soprattutto nei lanci con disponibilità scaglionata. Prima di acquistare conviene confrontare prezzo, recensioni aggiornate, requisiti tecnici e spazio necessario su disco.</p>
<p>Le date e le piattaforme riportate sono quelle comunicate per il lancio e possono essere soggette a variazioni regionali. Per gli acquisti digitali è inoltre utile controllare la lingua, i contenuti inclusi e le condizioni di rimborso dello store scelto.</p>"""
},
590:{
"slug":"pixel-10a-aumento-prezzo",
"title":"Google Pixel 10a: prezzo ufficiale e offerte, cosa è cambiato",
"seo":{"seo_title":"Google Pixel 10a: prezzo ufficiale 549 euro e offerte","seo_description":"Google Store indica Pixel 10a a 549 euro di listino e 449 euro in promozione. Le specifiche restano invariate: ecco cosa controllare prima dell'acquisto.","focus_keyphrase":"Google Pixel 10a prezzo"},
"max_words":220,
"content":"""<p>Il prezzo del Google Pixel 10a è stato al centro di segnalazioni contrastanti, ma la scheda del Google Store italiano consultata l'11 novembre 2026 mostra un prezzo di vendita abituale di 549 euro e una promozione a partire da 449 euro. Non risulta quindi corretto presentare 649 euro come nuovo listino ufficiale senza una conferma del produttore. Il prezzo effettivo può variare in base a promozioni, configurazione e rivenditore: prima di acquistare è sempre opportuno controllare la pagina ufficiale e il prezzo finale nel carrello.</p>
<h2>Che cosa offre Pixel 10a</h2>
<p>Pixel 10a è uno smartphone di fascia media che punta su software Google, fotografia computazionale e un display OLED ad alta frequenza. Lo schermo Actua misura circa 6,3 pollici, ha risoluzione 1.080 x 2.424 pixel e supporta una frequenza variabile fra 60 e 120 Hz. Il vetro Corning Gorilla Glass 7i protegge la parte frontale e la luminosità di picco dichiarata arriva fino a 3.000 nit in condizioni specifiche, un valore utile per la leggibilità all'aperto.</p>
<p>Google dichiara oltre 30 ore di autonomia con uso tipico e fino a 120 ore con Risparmio Energetico Estremo. Come sempre, i risultati reali dipendono da rete, luminosità, fotocamera, giochi e applicazioni utilizzate. La scelta del Pixel 10a è particolarmente interessante per chi preferisce un'esperienza Android pulita e gli aggiornamenti software integrati nell'ecosistema Google.</p>
<h2>Il prezzo è davvero aumentato?</h2>
<p>Il prezzo di vendita abituale indicato da Google Store è 549 euro, mentre la pagina consultata mostra una promozione a 449 euro. Questa distinzione è importante: un prezzo promozionale temporaneo non va confuso con il listino e una cifra riportata da un marketplace non dimostra da sola un aumento ufficiale. Se un rivenditore propone un prezzo molto diverso, bisogna verificare che si tratti della stessa capacità, di un prodotto nuovo e della versione destinata al mercato italiano.</p>
<h2>Come valutare un'offerta</h2>
<p>Prima di acquistare Pixel 10a conviene confrontare il prezzo con quello di altri smartphone della stessa fascia, controllare la memoria interna, verificare la provenienza del dispositivo e leggere le condizioni di garanzia e reso. Un prezzo inferiore non è automaticamente un affare se riguarda un modello importato, ricondizionato o venduto da un operatore non affidabile. Per chi valuta anche alternative Android di fascia superiore, può essere utile confrontare le caratteristiche di <a href="https://aivision.altervista.org/oppo-find-x10-e-pro-max-sconto-store-ufficiale/">OPPO Find X10 e Find X10 Pro Max</a>.</p>"""
},
587:{
"slug":"smart-tv-in-offerta-65-75-pollici",
"title":"Smart TV da 65 e 75 pollici: modelli e prezzi rilevati nelle offerte di ottobre",
"seo":{"seo_title":"Smart TV 65 e 75 pollici: modelli e prezzi di ottobre","seo_description":"Riepilogo delle offerte di ottobre 2026 per TV Haier, LG e Philips da 65 e 75 pollici. I prezzi riportati sono storici, non quotazioni attuali.","focus_keyphrase":"Smart TV 65 e 75 pollici"},
"max_words":230,
"content":"""<p>Le promozioni di ottobre 2026 hanno portato diversi televisori da 65 e 75 pollici sotto soglie di prezzo interessanti. Fra i modelli segnalati figuravano un Haier 4K con Google TV a 399,99 euro, un LG NanoCell AI da 65 pollici a 409 euro, un Philips Mini LED Quantum Dot da 65 pollici a 431 euro e un Philips da 75 pollici a 493 euro. Questi importi sono prezzi osservati nel periodo promozionale e vanno considerati come riferimento storico: non sono offerte garantite ancora disponibili oggi.</p>
<h2>65 pollici: la scelta più equilibrata per molti salotti</h2>
<p>Una diagonale da 65 pollici offre un'area di visione ampia senza richiedere lo spazio di un 75 pollici. Il modello Haier 4K con Google TV si rivolge a chi cerca una Smart TV essenziale con accesso alle principali app. LG NanoCell AI aggiunge l'elaborazione delle immagini tramite processore α7 e il sistema webOS, mentre il Philips Mini LED Quantum Dot punta su una gestione più evoluta della retroilluminazione e su una resa cromatica più ricca. Le differenze fra queste tecnologie contano più della sola diagonale: un pannello Mini LED può offrire un controllo della luminosità diverso rispetto a un LCD tradizionale, mentre la piattaforma smart determina l'accesso alle applicazioni e agli aggiornamenti.</p>
<h2>75 pollici: più immersione, ma servono distanza e spazio</h2>
<p>Il Philips 75PUS7000 da 75 pollici era stato segnalato a 493 euro nel periodo delle offerte. Uno schermo di queste dimensioni è interessante per film, sport e streaming, ma richiede una distanza di visione adeguata e una parete o un mobile sufficientemente ampi. Prima dell'acquisto è importante misurare larghezza del televisore, ingombro dei piedini e spazio per eventuale soundbar. La risoluzione 4K aiuta a mantenere una buona definizione anche su diagonali grandi, ma la qualità dipende anche da contrasto, luminosità e trattamento dei contenuti HDR.</p>
<h2>Che cosa controllare prima di comprare</h2>
<p>Non basta confrontare il prezzo: bisogna verificare il codice modello completo, la frequenza nativa del pannello, il supporto HDR, il numero di porte HDMI, la presenza di eARC e le funzioni gaming come ALLM e VRR. Per chi usa console di ultima generazione, un televisore limitato a 60 Hz non offre le stesse possibilità di un modello a 120 Hz. È utile anche controllare il sistema operativo, la disponibilità delle app preferite e la politica di aggiornamento.</p>
<p>Per un approfondimento su un modello specifico è disponibile la scheda della <a href="https://aivision.altervista.org/tv-lg-nanocell-ai-75-offerta-amazon/">LG NanoCell AI da 75 pollici</a>. Anche in quel caso il prezzo di ottobre è riportato come dato storico: prima di acquistare occorre verificare il prezzo corrente, il venditore, la spedizione e le condizioni di reso.</p>"""
}
}
def plain(s): return " ".join(html.unescape(re.sub(r"<[^>]+>"," ",s or "")).split())
def words(s): return len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ]+(?:['’][\wÀ-ÖØ-öø-ÿ]+)*\b",plain(s)))
def main():
 ap=argparse.ArgumentParser();ap.add_argument("mode",choices=["prepare","apply"]);mode=ap.parse_args().mode
 base=os.getenv("WP_BASE_URL","").rstrip("/").removesuffix("/wp-json");user=os.getenv("WP_USERNAME","");password=os.getenv("WP_APP_PASSWORD","")
 if base!=BASE or not user or not password: raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
 s=requests.Session();s.auth=(user,password);s.headers["User-Agent"]="AIVision-Commerce-Calendar-Article-Repair/1.0"
 def read(pid):
  r=s.get(f"{BASE}/wp-json/wp/v2/posts/{pid}",params={"context":"edit"},timeout=(8,30));r.raise_for_status();return r.json()
 if mode=="prepare":
  changes=[]
  for pid,spec in UPDATES.items():
   p=read(pid)
   if p.get("status")!="publish" or p.get("slug")!=spec["slug"]: raise RuntimeError(f"Post {pid}: stato o slug inatteso.")
   raw=(p.get("content") or {}).get("raw");seo=p.get("aivision_seo")
   if not isinstance(raw,str) or not isinstance(seo,dict) or words(raw)>spec["max_words"]: raise RuntimeError(f"Post {pid}: contenuto o SEO inatteso.")
   for link in re.findall(r'href="(https://aivision\.altervista\.org/[^"]+)"',spec["content"]):
    v=s.get(link,timeout=(8,25),allow_redirects=True)
    if v.status_code!=200 or not v.url.startswith(BASE+"/"): raise RuntimeError("Link interno non valido: "+link)
   after=dict(seo);after.update(spec["seo"])
   changes.append({"id":pid,"slug":spec["slug"],"modified":p.get("modified"),"before_content":raw,"after_content":spec["content"],"before_seo":seo,"after_seo":after,"before_words":words(raw),"after_words":words(spec["content"])})
  payload={"site":BASE,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"changes":changes}
  PLAN.parent.mkdir(parents=True,exist_ok=True);PLAN.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
  BACKUP.write_text(json.dumps({"site":BASE,"created_at":payload["created_at"],"posts":[{"id":x["id"],"slug":x["slug"],"modified":x["modified"],"content_raw":x["before_content"],"aivision_seo":x["before_seo"]} for x in changes]},ensure_ascii=False,indent=2),encoding="utf-8")
  for x in changes: print(f"Post {x['id']}: {x['before_words']} -> {x['after_words']} parole.")
  print("Backup pronto; nessuna modifica ancora eseguita.");return
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
