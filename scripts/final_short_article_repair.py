#!/usr/bin/env python3
"""Rivede sei articoli commerciali/auto, rimuove claim promozionali scaduti e salva backup."""
from __future__ import annotations
import argparse, datetime as dt, html, json, os, re
from pathlib import Path
import requests
BASE="https://aivision.altervista.org"
PLAN=Path("data/final_short_articles_plan.json")
BACKUP=Path("data/final_short_articles_backup.json")
RESULT=Path("data/final_short_articles_result.json")
UPDATES={
578:{
"slug":"sconto-dyson-coupon-100-euro",
"title":"Coupon Dyson DYS100: come funzionava lo sconto di ottobre",
"seo":{"seo_title":"Dyson DYS100: sconto di 100 euro, promozione scaduta","seo_description":"Il coupon Dyson DYS100 offriva 100 euro di sconto su ordini oltre 800 euro dal 2 all'11 ottobre 2026. Promozione terminata: condizioni e dettagli.","focus_keyphrase":"coupon Dyson DYS100"},
"max_words":180,
"content":"""<p>Il codice promozionale Dyson DYS100 era legato a una campagna sullo store ufficiale attiva dal 2 all'11 ottobre 2026. La promozione prevedeva una riduzione aggiuntiva di 100 euro sugli ordini che superavano 800 euro, con applicazione del codice nella fase di pagamento. La finestra promozionale è terminata: il coupon non va quindi considerato valido al momento della lettura e non è corretto presentare il ribasso come un'offerta ancora disponibile.</p>
<h2>Come funzionava il codice DYS100</h2>
<p>Durante il periodo indicato, il cliente doveva aggiungere al carrello prodotti Dyson sul sito ufficiale e inserire DYS100 nel campo dedicato ai codici promozionali. La soglia minima di 800 euro si riferiva al valore dell'ordine secondo le condizioni della campagna. Lo sconto era di 100 euro e non di una percentuale: su un carrello da 800 euro il risparmio nominale equivaleva al 12,5%, mentre su importi maggiori il peso percentuale diminuiva.</p>
<p>Il testo promozionale originario descriveva l'iniziativa come applicabile anche a prodotti già scontati. Tuttavia, le regole dei coupon possono contenere esclusioni, limiti per cliente, categorie non ammesse o condizioni di cumulabilità. Per questo non bisogna presumere che un codice sia combinabile con qualsiasi altra promozione senza leggere il regolamento mostrato al momento del checkout. Se il codice non viene accettato, il prezzo del carrello prima del pagamento è il riferimento decisivo.</p>
<h2>Quali prodotti potevano rientrare nell'iniziativa</h2>
<p>La soglia di spesa rendeva la promozione più adatta a ordini di valore elevato, ad esempio quando si acquistavano aspirapolvere, purificatori, asciugacapelli o più prodotti insieme. Prima di raggiungere artificialmente la soglia, però, era importante confrontare il prezzo dei singoli articoli con quello praticato da altri rivenditori: aggiungere un prodotto non necessario per ottenere 100 euro di sconto può annullare il vantaggio economico.</p>
<h2>Come valutare una nuova promozione Dyson</h2>
<p>Chi cerca oggi un'offerta dovrebbe verificare la data di validità, il valore minimo del carrello, i prodotti esclusi, la possibilità di cumulare il codice con gli sconti già presenti e le condizioni di reso. È utile confrontare il prezzo finale, non soltanto il valore del coupon. Le promozioni Dyson possono cambiare rapidamente e un codice pubblicato in un articolo precedente non deve essere considerato attivo senza una conferma sul sito ufficiale.</p>
<p>Il codice DYS100 resta quindi un riferimento storico alla campagna del 2-11 ottobre 2026. Questa pagina conserva i dettagli per chi desidera ricostruire l'iniziativa, ma non segnala una promozione attualmente sottoscrivibile.</p>"""
},
563:{
"slug":"crucial-p310-1tb-offerta-amazon",
"title":"Crucial P310 1TB: specifiche dell'SSD PCIe 4.0 e prezzo della vecchia offerta",
"seo":{"seo_title":"Crucial P310 1TB: velocità, formato e prezzo storico","seo_description":"Crucial P310 1TB M.2 2280 raggiunge 7.100 MB/s in lettura e 6.000 MB/s in scrittura. I 154,98 euro erano il prezzo della promozione originaria.","focus_keyphrase":"Crucial P310 1TB"},
"max_words":260,
"content":"""<p>Crucial P310 da 1 TB è un SSD interno NVMe pensato per PC desktop e notebook compatibili. Il modello M.2 2280 utilizza l'interfaccia PCIe 4.0 x4 e dichiara velocità sequenziali fino a 7.100 MB/s in lettura e 6.000 MB/s in scrittura. Nell'articolo originario era segnalato a 154,98 euro con uno sconto del 30% su Amazon: quel prezzo è una rilevazione promozionale dell'autunno 2026 e non va considerato una quotazione attuale garantita.</p>
<h2>Specifiche e prestazioni</h2>
<p>Il P310 1TB con codice CT1000P310SSD8 è un'unità M.2 2280 PCIe 4.0 NVMe. Le velocità massime dichiarate dal produttore sono valori di laboratorio e rappresentano un limite teorico in condizioni favorevoli: le prestazioni effettive dipendono da scheda madre, dissipazione, spazio libero, tipo di carico e gestione della cache. Nei trasferimenti prolungati la velocità può variare rispetto ai picchi sequenziali indicati nella scheda tecnica.</p>
<p>Il modello utilizza memoria NAND QLC e una cache dinamica, senza DRAM dedicata; può quindi offrire ottime prestazioni in lettura e nei carichi brevi, ma non è automaticamente la scelta migliore per scritture intensive e continue. La versione da 1 TB è indicata con una resistenza nominale di 220 TBW e garanzia limitata di cinque anni secondo le condizioni del produttore. È opportuno verificare il codice prodotto esatto, perché la famiglia P310 comprende anche varianti con formato M.2 2230 destinate a dispositivi più compatti.</p>
<h2>Compatibilità: controllare il formato prima dell'acquisto</h2>
<p>Il formato 2280 misura 22 millimetri in larghezza e 80 in lunghezza. Prima di acquistare bisogna verificare che il computer disponga di uno slot M.2 NVMe compatibile con PCIe 4.0 e che ci sia spazio sufficiente per l'unità e per l'eventuale dissipatore. Non va confuso con la versione 2230, molto più corta, utilizzata da alcuni dispositivi portatili. Anche la presenza di uno slot M.2 non garantisce da sola la compatibilità: alcuni sistemi supportano soltanto SATA o limitano le dimensioni installabili.</p>
<h2>Per gaming e produttività</h2>
<p>Un SSD PCIe 4.0 veloce può ridurre i tempi di avvio del sistema, caricamento dei giochi e apertura di file pesanti. Il vantaggio percepito dipende però dal carico: passare da un SSD SATA a un NVMe può essere evidente in alcune operazioni, mentre la differenza fra due SSD NVMe moderni può risultare meno marcata nell'uso quotidiano. Per un PC da lavoro con grandi trasferimenti frequenti può essere utile valutare anche capacità, resistenza alle scritture e presenza di DRAM.</p>
<h2>Il prezzo di 154,98 euro</h2>
<p>Il prezzo di 154,98 euro citato nell'articolo era associato a una promozione Amazon con sconto dichiarato del 30%. Non è un prezzo corrente verificato. Prima di acquistare oggi occorre controllare il venditore, il codice CT1000P310SSD8, la presenza o meno del dissipatore, le condizioni di garanzia e il prezzo finale al checkout. Un confronto con altri SSD PCIe 4.0 da 1 TB aiuta a capire se l'offerta è davvero competitiva.</p>"""
},
581:{
"slug":"e-bike-in-carbonio-engwe-n1-pro-air-doppio-sconto",
"title":"ENGWE N1 Pro e N1 Air: differenze tra le e-bike in carbonio",
"seo":{"seo_title":"ENGWE N1 Pro e N1 Air: motore, peso e autonomia","seo_description":"Confronto ENGWE N1 Pro e N1 Air: telaio in carbonio, motore centrale o al mozzo, batteria 360 Wh, autonomia dichiarata e peso.","focus_keyphrase":"ENGWE N1 Pro e N1 Air"},
"max_words":190,
"content":"""<p>ENGWE N1 Pro e N1 Air sono due city e-bike con telaio in fibra di carbonio, ma adottano soluzioni tecniche differenti. La N1 Pro punta su un motore centrale con coppia elevata e un allestimento più ricco; la N1 Air privilegia il peso contenuto e un motore al mozzo posteriore. L'articolo originario parlava di un doppio sconto autunnale: quella campagna non va considerata ancora attiva e i prezzi mostrati oggi sullo store possono essere diversi.</p>
<h2>ENGWE N1 Pro: motore centrale e 80 Nm</h2>
<p>La N1 Pro utilizza un motore centrale Ananda brushless da 250 W con sensore di coppia e una coppia dichiarata di 80 Nm. La batteria rimovibile è da 36 V e 10 Ah, pari a 360 Wh, e l'autonomia massima indicata dal produttore arriva a 100 km al livello di assistenza PAS 1. Il valore è una stima in condizioni favorevoli: peso del ciclista, dislivello, temperatura, pressione degli pneumatici e livello di assistenza possono ridurre sensibilmente la distanza percorribile.</p>
<p>La bici pesa circa 19 kg, monta ruote 700x42C, cambio Shimano a sette rapporti e freni a disco idraulici. Il motore centrale trasferisce la potenza alla trasmissione e può offrire una sensazione più naturale quando si affrontano salite o variazioni di ritmo. La presenza di GPS, geofencing e blocco smart amplia le funzioni antifurto, ma non sostituisce un lucchetto fisico robusto.</p>
<h2>ENGWE N1 Air: più leggera e con motore al mozzo</h2>
<p>La N1 Air utilizza un motore posteriore Mivice da 250 W con sensore di coppia e 40 Nm. La batteria rimovibile Samsung da 36 V e 10 Ah offre la stessa capacità nominale di 360 Wh e l'autonomia dichiarata arriva anch'essa a 100 km in PAS 1. Il peso indicato è di circa 15,6 kg per la versione standard; la variante ST può avere un peso differente. La trasmissione è Shimano a sette velocità e sono disponibili configurazioni con freni meccanici o idraulici.</p>
<h2>Quale scegliere?</h2>
<p>N1 Pro è più adatta a chi affronta salite e desidera la coppia più elevata del motore centrale. N1 Air è interessante per chi deve trasportare spesso la bici, salire scale o privilegiare la leggerezza. Entrambe sono limitate a 25 km/h di assistenza secondo la configurazione dichiarata per il mercato europeo; per circolare su strada è comunque necessario rispettare la normativa locale e verificare che la versione acquistata sia conforme alla categoria delle biciclette a pedalata assistita.</p>
<h2>Prezzi e promozioni</h2>
<p>Le pagine ufficiali ENGWE mostrano prezzi e disponibilità che possono cambiare per variante, paese e periodo. La promozione con doppio sconto citata nell'articolo originale era legata a link e condizioni temporanee e non va considerata valida senza una verifica sul carrello. Prima di acquistare conviene confrontare il prezzo finale, il tipo di freni, la garanzia, il servizio di assistenza e il costo di eventuali ricambi.</p>"""
},
551:{
"slug":"leapmotor-b03x-prova-prezzi-consumi",
"title":"Leapmotor B03X: consumi WLTP, autonomia e prezzi aggiornati",
"seo":{"seo_title":"Leapmotor B03X: consumi, autonomia e prezzi aggiornati","seo_description":"Leapmotor B03X: batterie da 39,8 e 53 kWh, autonomia WLTP fino a 382 km e consumo dichiarato di 15,5-15,7 kWh/100 km.","focus_keyphrase":"Leapmotor B03X consumi"},
"max_words":170,
"content":"""<p>Leapmotor B03X è un B-SUV elettrico distribuito in Italia attraverso la rete Stellantis. L'articolo originario riportava un consumo medio di 13,5 kWh/100 km come dato di una prova su strada, ma quel valore non coincide con il consumo ufficiale comunicato per il modello e non deve essere presentato come un risultato verificato da un test indipendente. Per confrontare le versioni è più corretto partire dai dati omologati WLTP e distinguere chiaramente questi valori dai consumi reali.</p>
<h2>Due batterie e due livelli di potenza</h2>
<p>La gamma italiana comprende una batteria LFP da 39,8 kWh abbinata a un motore da 130 kW, pari a 176 CV, con autonomia fino a 292 km WLTP. La seconda configurazione utilizza una batteria da 53 kWh e un motore da 145 kW, pari a 197 CV, con autonomia dichiarata fino a 382 km WLTP. Entrambe le versioni adottano trazione anteriore e sono progettate per l'uso urbano e per gli spostamenti extraurbani, con differenze di autonomia legate soprattutto alla capacità della batteria.</p>
<h2>Consumo e ricarica</h2>
<p>Il consumo dichiarato si colloca intorno a 15,5-15,7 kWh per 100 km a seconda della versione e della configurazione. Il dato WLTP è ottenuto con una procedura standardizzata e non rappresenta una promessa di percorrenza in qualsiasi condizione. In autostrada, con temperature basse, climatizzazione attiva o velocità elevate, il consumo può aumentare; in città e con guida regolare può risultare più favorevole.</p>
<p>La ricarica rapida in corrente continua permette di passare dal 30% all'80% in circa 16 minuti secondo i dati del produttore, in condizioni compatibili con la potenza di ricarica disponibile. Il tempo reale dipende da temperatura della batteria, potenza della colonnina e curva di ricarica.</p>
<h2>Prezzi e promozioni in Italia</h2>
<p>Il listino di partenza è di 24.900 euro per la versione Life da 39,8 kWh, 27.400 euro per la Life da 53 kWh e 29.400 euro per la Design da 53 kWh. Alla data dell'11 novembre 2026, il sito Leapmotor indicava una promozione con prezzi a partire da 20.900 euro per la versione d'ingresso, valida fino al 30 novembre 2026 secondo le condizioni pubblicate. Il prezzo promozionale può dipendere da requisiti, permuta, finanziamento e disponibilità: va verificato presso il concessionario prima di firmare.</p>
<h2>Come leggere i dati di autonomia</h2>
<p>Per scegliere la versione giusta è utile stimare i chilometri percorsi in una settimana, la possibilità di ricaricare a casa e la frequenza dei viaggi autostradali. La batteria da 53 kWh offre più margine sulle percorrenze lunghe, mentre la versione da 39,8 kWh può essere sufficiente per un uso prevalentemente urbano. I consumi reali andrebbero confrontati solo fra prove svolte in condizioni simili, non con un singolo valore isolato.</p>
<p>Per le dimensioni, le dotazioni e il posizionamento del modello è disponibile anche la scheda introduttiva sulla <a href="https://aivision.altervista.org/leapmotor-b03x/">Leapmotor B03X</a>.</p>"""
},
548:{
"slug":"dji-osmo-pocket-3-offerta-amazon",
"title":"DJI Osmo Pocket 3: sensore da 1 pollice, 4K/120 e stabilizzazione",
"seo":{"seo_title":"DJI Osmo Pocket 3: sensore 1 pollice e video 4K/120","seo_description":"DJI Osmo Pocket 3 integra sensore CMOS da 1 pollice, gimbal a 3 assi, display ruotabile da 2 pollici e video 4K/120 in slow motion.","focus_keyphrase":"DJI Osmo Pocket 3"},
"max_words":200,
"content":"""<p>DJI Osmo Pocket 3 è una videocamera tascabile con gimbal meccanico a tre assi, progettata per vlog, viaggi e riprese in movimento. L'articolo originale la presentava al prezzo minimo storico su Amazon, ma quella segnalazione non rappresenta una quotazione attuale verificata. Il valore del prodotto dipende soprattutto dal formato compatto e dalla possibilità di ottenere filmati stabilizzati senza portare con sé una fotocamera più ingombrante.</p>
<h2>Sensore da 1 pollice e registrazione video</h2>
<p>La Pocket 3 utilizza un sensore CMOS da 1 pollice e un obiettivo equivalente a 20 mm con apertura f/2.0. Il sensore più grande rispetto a quello di molte action camera tascabili aiuta a raccogliere luce e a conservare dettaglio, soprattutto nelle scene con illuminazione non ideale. La registrazione standard arriva fino a 4K a 60 fotogrammi al secondo; la modalità 4K/120 è riservata allo slow motion e non va confusa con la registrazione continua in 4K a 120 fps.</p>
<p>Il dispositivo supporta profili colore a 10 bit D-Log M e HLG, utili per chi vuole maggiore flessibilità in post-produzione. Il sistema di messa a fuoco rapida a pixel interi e le funzioni di ottimizzazione dell'immagine sono pensati per mantenere il soggetto leggibile anche quando si registra camminando o cambiando rapidamente inquadratura.</p>
<h2>Gimbal a tre assi e display ruotabile</h2>
<p>La stabilizzazione meccanica a tre assi compensa i movimenti della mano e permette riprese più fluide rispetto alla sola stabilizzazione elettronica. Il touchscreen da 2 pollici ruota per passare dall'inquadratura orizzontale a quella verticale, rendendo più semplice creare contenuti per social e piattaforme video. ActiveTrack 6.0 aiuta a mantenere il soggetto nell'inquadratura, mentre la compatibilità con DJI Mic 2 e Mic Mini consente di migliorare l'audio con microfoni wireless compatibili.</p>
<h2>Autonomia, ricarica e limiti pratici</h2>
<p>La batteria integrata è da 1.300 mAh. DJI indica una ricarica fino all'80% in circa 16 minuti e completa in circa 32 minuti con un caricatore PD da 65 W, in condizioni di laboratorio. La durata effettiva dipende da risoluzione, frame rate, temperatura, luminosità dello schermo e uso del Wi-Fi. La registrazione 4K/120 in slow motion è inoltre limitata dalla gestione termica e dalla durata massima del singolo clip indicata dal produttore.</p>
<h2>Per chi è indicata</h2>
<p>Osmo Pocket 3 è adatta a chi registra spesso video in movimento e vuole un dispositivo leggero con stabilizzazione meccanica e buona qualità d'immagine. È meno indicata per chi cerca una action camera impermeabile da usare senza protezione in acqua o in condizioni estreme. Prima dell'acquisto conviene confrontare il prezzo corrente, la Creator Combo, gli accessori inclusi e la disponibilità di microfoni e impugnature. Il prezzo minimo storico citato nell'articolo originario era legato a una promozione Amazon passata e non va considerato attivo oggi.</p>"""
},
524:{
"slug":"leapmotor-b03x",
"title":"Leapmotor B03X: dimensioni, batterie, dotazioni e prezzi in Italia",
"seo":{"seo_title":"Leapmotor B03X: dimensioni, batterie e prezzi in Italia","seo_description":"La Leapmotor B03X è un B-SUV elettrico da 4,27 metri con batterie LFP da 39,8 o 53 kWh, autonomia WLTP fino a 382 km e prezzi da 24.900 euro.","focus_keyphrase":"Leapmotor B03X"},
"max_words":170,
"content":"""<p>Leapmotor B03X è un crossover elettrico compatto sviluppato per il segmento B-SUV e distribuito in Italia attraverso la rete Stellantis. La carrozzeria misura circa 4,27 metri e il progetto punta a combinare abitabilità, dotazioni digitali e un prezzo di accesso più contenuto rispetto a molti SUV elettrici di dimensioni superiori. La gamma italiana comprende due capacità di batteria e più allestimenti, perciò è importante non confondere il prezzo promozionale della versione d'ingresso con quello delle configurazioni più potenti.</p>
<h2>Dimensioni e impostazione del progetto</h2>
<p>La B03X è pensata per l'uso quotidiano in città ma mantiene dimensioni adatte anche a spostamenti extraurbani. La trazione è anteriore e l'architettura Cell-to-Chassis integra la batteria nella struttura del veicolo, con l'obiettivo di migliorare rigidità e gestione dello spazio. L'abitacolo è dominato da un'impostazione digitale e da sistemi di assistenza alla guida di livello 2; le dotazioni esatte possono variare in base alla versione e al mercato.</p>
<h2>Batteria, motore e autonomia WLTP</h2>
<p>La versione Life di accesso utilizza una batteria LFP da 39,8 kWh e un motore da 130 kW, pari a 176 CV, con autonomia dichiarata fino a 292 km nel ciclo WLTP. La configurazione da 53 kWh abbina un motore da 145 kW, pari a 197 CV, e arriva fino a 382 km WLTP. Il dato di omologazione non coincide con la percorrenza garantita in ogni condizione: temperatura, velocità, carico e climatizzazione possono modificare sensibilmente l'autonomia reale.</p>
<p>La ricarica rapida in corrente continua permette di passare dal 30% all'80% in circa 16 minuti secondo i dati del produttore, quando batteria e colonnina operano nelle condizioni previste. Per la ricarica domestica è invece utile valutare la potenza del caricatore di bordo e il tempo necessario per ripristinare l'energia durante la notte.</p>
<h2>Prezzi e promozione italiana</h2>
<p>Il listino italiano parte da 24.900 euro per la Life da 39,8 kWh, passa a 27.400 euro per la Life da 53 kWh e arriva a 29.400 euro per la Design da 53 kWh. Alla data dell'11 novembre 2026, il sito ufficiale indicava prezzi promozionali a partire da 20.900 euro per la versione d'ingresso, con campagna valida fino al 30 novembre 2026. La promozione può essere legata a requisiti commerciali, permuta o finanziamento: il prezzo effettivo va verificato per iscritto con il concessionario.</p>
<h2>Quale versione scegliere</h2>
<p>La batteria da 39,8 kWh può essere sufficiente per chi percorre soprattutto tragitti urbani e dispone di ricarica regolare. La versione da 53 kWh offre più autonomia e potenza, risultando più adatta a chi affronta viaggi frequenti o percorrenze miste. Prima di scegliere conviene confrontare costo totale, tempi di ricarica, dotazioni incluse e condizioni della promozione, non soltanto il prezzo pubblicizzato. Per consumi e differenze fra le configurazioni è disponibile anche l'approfondimento sulla <a href="https://aivision.altervista.org/leapmotor-b03x-prova-prezzi-consumi/">Leapmotor B03X e i suoi consumi dichiarati</a>.</p>"""
}
}
def plain(s): return " ".join(html.unescape(re.sub(r"<[^>]+>"," ",s or "")).split())
def words(s): return len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ]+(?:['’][\wÀ-ÖØ-öø-ÿ]+)*\b",plain(s)))
def main():
 ap=argparse.ArgumentParser();ap.add_argument("mode",choices=["prepare","apply"]);mode=ap.parse_args().mode
 base=os.getenv("WP_BASE_URL","").rstrip("/").removesuffix("/wp-json");user=os.getenv("WP_USERNAME","");password=os.getenv("WP_APP_PASSWORD","")
 if base!=BASE or not user or not password: raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
 s=requests.Session();s.auth=(user,password);s.headers["User-Agent"]="AIVision-Final-Short-Article-Repair/1.0"
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
  print("Backup pronto; nessuna scrittura ancora eseguita.");return
 plan=json.loads(PLAN.read_text(encoding="utf-8"))
 if plan.get("site")!=BASE or len(plan.get("changes",[]))!=6: raise RuntimeError("Piano non valido.")
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
