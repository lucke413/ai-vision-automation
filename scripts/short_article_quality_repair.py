#!/usr/bin/env python3
"""Revisione mirata degli articoli brevi: corregge affermazioni, amplia il valore informativo e cita fonti."""
from __future__ import annotations
import argparse, datetime as dt, json, os
from pathlib import Path
from public_source_links import clean_source_links

import requests

BASE = "https://aivision.altervista.org"
PLAN = Path("data/short_article_quality_plan.json")
BACKUP = Path("data/short_article_quality_backup.json")
RESULT = Path("data/short_article_quality_result.json")
MARKER = "<!-- ai-vision-short-quality-update:v1 -->"

UPDATES = {
518: {
 "slug": "nuova-fire-tv-stick-4k-disponibile-sconto",
 "title": "Fire TV Stick 4K 2026: specifiche, Vega OS e prezzo di lancio",
 "seo": {"seo_title": "Fire TV Stick 4K 2026: specifiche e prezzo",
         "seo_description": "Fire TV Stick 4K 2026 usa Vega OS, Wi-Fi 6 e 4K HDR10+. La promozione di lancio da 35,99 euro è terminata il 12 ottobre.",
         "focus_keyphrase": "Fire TV Stick 4K 2026"},
 "mode": "append",
 "html": """<h2>Specifiche ufficiali e differenze rispetto alla versione Max</h2>
<p>La scheda tecnica Amazon identifica il modello come Fire TV Stick 4K di terza generazione (2026), con sistema operativo Vega OS 2.0, processore MediaTek MT8698E, 1 GB di RAM, connettore HDMI 2.1 e porta USB-C. La connettività comprende Wi-Fi 6 e la riproduzione 4K con HDR10+. Non va confusa con la 4K Max: quest'ultima resta il modello superiore della gamma e include funzioni home theater aggiuntive come Dolby Vision e Dolby Atmos, oltre a più memoria.</p>
<p>Il prezzo di 35,99 euro era il prezzo promozionale di lancio annunciato da Amazon e valido fino al 12 ottobre 2026; non è quindi corretto presentarlo come sconto ancora attivo. Il prezzo attuale può variare e va verificato sulla pagina Amazon al momento dell'acquisto. Anche la disponibilità di Alexa+ dipende dal rollout e dalle condizioni dell'accesso anticipato descritte da Amazon.</p>
<p class="av-source-reference">Fonti: <a href="https://www.aboutamazon.it/notizie/dispositivi-amazon/nuova-fire-tv-stick-4k-veloce-design-rinnovato" rel="noopener noreferrer">Amazon Italia – lancio, prezzo e telecomando della Fire TV Stick 4K</a>; <a href="https://developer.amazon.com/docs/fire-tv/device-specifications-fire-tv-streaming-media-player.html?v=ftvstick4k_2026" rel="noopener noreferrer">Amazon Developer – specifiche tecniche ufficiali del modello 2026</a>.</p>"""
},
557: {
 "slug": "chatgpt-virtual-try-on-prova-vestiti",
 "title": "ChatGPT: prova virtuale dei vestiti e raccolta dei preferiti",
 "seo": {"seo_title": "ChatGPT: prova virtuale e preferiti",
         "seo_description": "La prova virtuale di ChatGPT usa un selfie per visualizzare abiti e accessori. La foto di riferimento si può modificare o eliminare dalle impostazioni.",
         "focus_keyphrase": "prova virtuale vestiti ChatGPT"},
 "mode": "replace",
 "html": """<p>Il 1° ottobre 2026 OpenAI ha annunciato nuovi strumenti per lo shopping in ChatGPT: la prova virtuale di vestiti e accessori e la possibilità di salvare i prodotti preferiti. Le funzioni sono disponibili su ChatGPT per dispositivi mobili e web. Le note ufficiali non indicano che ogni funzione sia identica su tutti i piani o in ogni Paese: la disponibilità può dipendere dal rollout del servizio.</p>
<h2>Come funziona la prova virtuale</h2>
<p>Quando compare il pulsante “Prova” nella scheda di un prodotto di abbigliamento o accessorio, l'utente può selezionarlo e scattare o caricare un selfie. ChatGPT Images genera quindi un'immagine di anteprima che mostra come potrebbe apparire il capo sulla persona. Si tratta di una simulazione visiva: non garantisce vestibilità, taglia, materiale, colore reale o risultato identico a una prova fisica. Prima dell'acquisto è quindi necessario consultare la guida alle taglie e le informazioni del venditore.</p>
<h2>Foto di riferimento e privacy</h2>
<p>OpenAI specifica che la foto di riferimento viene salvata per rendere più rapide le prove successive. L'utente può cambiarla o eliminarla da Impostazioni, Personalizzazione, Foto di riferimento. È una scelta importante da conoscere prima di caricare un'immagine personale: conviene usare una foto appropriata, evitare immagini di altre persone senza consenso e controllare periodicamente le impostazioni disponibili nel proprio account.</p>
<h2>Come salvare i prodotti preferiti</h2>
<p>La funzione Preferiti consente di salvare i prodotti individuati durante la ricerca e organizzarli in cartelle nella Libreria di ChatGPT. In questo modo si possono confrontare più opzioni e ritrovare i collegamenti in un secondo momento. ChatGPT non conclude direttamente l'acquisto: per prezzo, taglia, disponibilità, spedizione, resi e pagamento bisogna verificare le condizioni sul sito del rivenditore.</p>
<p class="av-source-reference">Fonte ufficiale: <a href="https://help-lb.openai.com/it-it/articles/6825453-chatgpt-release-notes" rel="noopener noreferrer">OpenAI – Note di rilascio di ChatGPT, 1° ottobre 2026</a>.</p>"""
},
596: {
 "slug": "fuga-d-emergenza-tesla-ricarica",
 "title": "Tesla: come sbloccare manualmente un cavo di ricarica bloccato",
 "seo": {"seo_title": "Tesla: sbloccare il cavo di ricarica in sicurezza",
         "seo_description": "La procedura Tesla di rilascio manuale si usa solo dopo aver fermato la ricarica. Non scollegare il cavo mentre il veicolo sta caricando.",
         "focus_keyphrase": "sbloccare cavo ricarica Tesla"},
 "mode": "replace",
 "html": """<p>Un cavo di ricarica che non si sgancia può creare una situazione scomoda, ma non va affrontata forzando il connettore o tentando di spostare l'auto mentre è collegata. La documentazione Tesla descrive una procedura di rilascio manuale per alcuni modelli quando i metodi normali non funzionano. Non è una funzione che autorizza a partire con il cavo ancora collegato e non deve essere eseguita mentre la vettura sta caricando.</p>
<h2>Prima prova i comandi normali</h2>
<p>Usa il pulsante sul connettore, il touchscreen del veicolo o l'app Tesla per interrompere la sessione e sbloccare il cavo. Controlla sul display che la ricarica sia effettivamente terminata. Se il connettore resta bloccato, consulta il manuale della tua versione esatta: la posizione del dispositivo di rilascio manuale può cambiare in base a modello e anno.</p>
<h2>La procedura manuale documentata per Model Y</h2>
<p>Nel manuale Model Y, Tesla indica di verificare prima che il veicolo non stia caricando e, se necessario, selezionare “Interrompi ricarica”. Solo dopo si apre il portellone posteriore e si tira verso il basso il cavo di rilascio della porta di ricarica, che sblocca il connettore. Il cavo di ricarica va rimosso soltanto dopo aver completato il rilascio manuale. Questa procedura è specifica del modello descritto nel manuale e non va trasferita automaticamente ad altre Tesla.</p>
<h2>Avvertenze importanti</h2>
<p>Tesla avverte di non tirare il cavo di rilascio mentre si tenta contemporaneamente di estrarre il connettore: prima si aziona il rilascio, poi si rimuove il cavo. Non eseguire la procedura se il veicolo sta caricando o se sono visibili conduttori arancioni ad alta tensione. L'uso continuativo del rilascio manuale può danneggiare il cavo o l'attrezzatura; se non sei certo della procedura, contatta un centro assistenza Tesla. In caso di dubbi, non forzare mai il connettore.</p>
<p class="av-source-reference">Fonte tecnica: <a href="https://www.tesla.com/ownersmanual/modely/en_eu/GUID-BEE08D47-0CE0-4BDD-83F2-9854FB3D578F.html" rel="noopener noreferrer">Manuale ufficiale Tesla Model Y – rilascio manuale del cavo di ricarica</a>.</p>"""
},
572: {
 "slug": "telecamera-apple-senza-video-ia-privacy",
 "title": "Apple e la telecamera domestica AI: cosa dicono le indiscrezioni",
 "seo": {"seo_title": "Apple: indiscrezioni sulla telecamera AI",
         "seo_description": "Bloomberg riferisce di una possibile telecamera Apple per la casa nel 2027. Il progetto non è stato annunciato ufficialmente e i dettagli restano indiscrezioni.",
         "focus_keyphrase": "telecamera Apple casa AI"},
 "mode": "replace",
 "html": """<p>Apple starebbe valutando una telecamera di sicurezza domestica basata sull'intelligenza artificiale, ma il prodotto non è stato annunciato ufficialmente. Le informazioni disponibili derivano da indiscrezioni attribuite a Bloomberg e riprese da testate tecnologiche: non costituiscono una scheda tecnica confermata né una promessa di lancio da parte di Apple.</p>
<h2>Che cosa riportano le indiscrezioni</h2>
<p>Secondo il resoconto pubblicato da MacRumors il 4 settembre 2026, Apple starebbe lavorando a un sistema per la casa con una telecamera capace di analizzare gli eventi e generare descrizioni testuali, invece di basarsi necessariamente sulla registrazione di filmati tradizionali. Il progetto sarebbe collegato a un servizio di sicurezza domestica e a un hub per la smart home. Non sono però confermati nome commerciale, design definitivo, prezzo, data di lancio o specifiche del sensore.</p>
<p>La parte più interessante dell'ipotesi riguarda l'elaborazione dei dati e la privacy: un sistema che descrive gli eventi senza conservare un archivio video potrebbe ridurre la quantità di immagini memorizzate. Tuttavia, finché Apple non pubblicherà dettagli tecnici, non è possibile affermare che l'elaborazione avverrà interamente in locale, che nessun dato verrà trasmesso o che il dispositivo non registrerà mai immagini. Queste conclusioni sarebbero premature.</p>
<h2>Che cosa offre già Apple</h2>
<p>La funzione HomeKit Secure Video è già disponibile con telecamere di terze parti compatibili e permette di gestire notifiche e registrazioni protette secondo il piano iCloud+ e i requisiti del dispositivo. È un prodotto distinto dalla telecamera ipotizzata nelle indiscrezioni. Chi cerca oggi una soluzione per la casa deve quindi valutare i dispositivi HomeKit effettivamente in commercio, le aree riprese, la conservazione dei filmati e le impostazioni di condivisione.</p>
<p>In assenza di un annuncio ufficiale, le informazioni sul possibile dispositivo Apple vanno considerate provvisorie e soggette a cambiamenti.</p>
<p class="av-source-reference">Fonti: <a href="https://www.macrumors.com/2026/09/04/apple-home-security-camera-2027/" rel="noopener noreferrer">MacRumors – indiscrezioni attribuite a Bloomberg, 4 settembre 2026</a>; <a href="https://www.apple.com/it/home-app/" rel="noopener noreferrer">Apple – app Casa e funzioni per la smart home</a>.</p>"""
},
542: {
 "slug": "circuito-europeo-pagamenti-enp",
 "title": "ENP: la rete europea che collega Bancomat, Bizum, Wero, MB Way e Vipps",
 "seo": {"seo_title": "ENP: la rete europea dei pagamenti",
         "seo_description": "European Network for Payments collega cinque soluzioni europee. La prima fase riguarda i pagamenti P2P; e-commerce e POS arriveranno in fasi successive.",
         "focus_keyphrase": "European Network for Payments ENP"},
 "mode": "replace",
 "html": """<p>European Network for Payments (ENP) è una nuova entità di interoperabilità creata da Bancomat, Bizum, EPI/Wero, SIBS–MB WAY e Vipps MobilePay. L'obiettivo è collegare le rispettive soluzioni di pagamento basate su trasferimenti da conto a conto, così che gli utenti possano utilizzare il servizio che già conoscono anche quando si trovano in un altro Paese europeo. Non si tratta, almeno nella fase iniziale, di una nuova carta europea che sostituisce automaticamente Visa e Mastercard.</p>
<h2>Chi partecipa e quanti utenti può raggiungere</h2>
<p>La società è stata costituita a Madrid ed è sostenuta dai cinque partner fondatori. Secondo l'annuncio ufficiale di EPI, le soluzioni coinvolte servono complessivamente circa 130 milioni di utenti in 14 Paesi europei. La cifra indica la platea potenziale delle soluzioni aderenti, non il numero di persone che possono già effettuare ogni tipo di pagamento in tutti i Paesi.</p>
<h2>Il calendario: prima P2P, poi negozi ed e-commerce</h2>
<p>L'implementazione sarà graduale. La prima fase riguarda i pagamenti transfrontalieri tra persone (P2P); in seguito l'interoperabilità dovrà estendersi agli acquisti online e ai pagamenti nei punti vendita fisici (POS). Questo significa che la nascita di ENP non rende immediatamente utilizzabili Bancomat Pay, Bizum, Wero, MB WAY e Vipps in qualsiasi negozio europeo: disponibilità, banche aderenti e casi d'uso dipenderanno dai rollout e dagli accordi dei singoli partner.</p>
<h2>La guida operativa e il nuovo CEO</h2>
<p>Il 10 novembre 2026 EPI ha annunciato la nomina di William Olgiati a CEO di ENP, con effetto dal 21 ottobre. Olgiati proviene da Amazon, dove ha lavorato per 14 anni nell'ambito dell'accettazione dei pagamenti in Europa e nel Regno Unito. La nomina segna il passaggio dalla costituzione della società alla fase di sviluppo operativo e tecnico della rete.</p>
<p>Per ora ENP va considerata un progetto di interoperabilità in costruzione, non un circuito di carte già pienamente operativo. Le commissioni per esercenti e consumatori, le date di attivazione dei singoli servizi e la copertura concreta dovranno essere comunicate dai partner man mano che il progetto avanzerà.</p>
<p class="av-source-reference">Fonti: <a href="https://epicompany.eu/media-insights/ceo-european-network-for-payments/" rel="noopener noreferrer">EPI Company – nomina di William Olgiati a CEO di ENP, 10 novembre 2026</a>; <a href="https://epicompany.eu/media-insights/" rel="noopener noreferrer">EPI Company – comunicati ufficiali su ENP e Wero</a>; <a href="https://www.pmi.it/tecnologia/prodotti-e-servizi-ict/487105/pagamenti-ue-bancomat-sfida-visa-mastercard-calo-commissioni.html" rel="noopener noreferrer">PMI.it – fasi e limiti operativi della rete</a>.</p>"""
},
545: {
 "slug": "the-witcher-3-remastered-problemi-performance-soluzioni",
 "title": "The Witcher 3 Remastered: patch 5.01 corregge bug e prestazioni",
 "seo": {"seo_title": "The Witcher 3 Remastered: patch 5.01",
         "seo_description": "Dopo l'hotfix 5.00c, CD Projekt RED ha pubblicato la patch 5.01 di The Witcher 3 Remastered con correzioni per PC e console.",
         "focus_keyphrase": "The Witcher 3 Remastered patch 5.01"},
 "mode": "replace",
 "html": """<p>The Witcher 3: Wild Hunt — Remastered è arrivato il 29 settembre 2026. Il lancio è stato accompagnato da segnalazioni di problemi tecnici su PC e console; CD Projekt RED ha pubblicato prima l'hotfix 5.00c e poi la patch 5.01, con interventi su stabilità, grafica, salvataggi e prestazioni.</p>
<h2>Hotfix 5.00c: i primi problemi corretti</h2>
<p>L'hotfix 5.00c, pubblicato il 1° ottobre per la versione PC, ha corretto fra l'altro i problemi di salvataggio e caricamento quando il percorso della cartella Documenti conteneva caratteri speciali, l'abbassamento del volume del doppiaggio dopo l'uso del menu di pausa e alcuni difetti grafici in Velen. CD Projekt RED ha inoltre annullato una modifica che causava problemi di prestazioni e resa visiva con Nvidia HairWorks attivo.</p>
<h2>Patch 5.01: interventi su PC e console</h2>
<p>La patch 5.01 è stata pubblicata l'8 ottobre 2026 su PC, PlayStation 5 e Xbox Series X|S. Le note ufficiali elencano correzioni al comportamento di schivate e abilità, alla gestione degli oli per le lame, ai menu e alle barre di avanzamento. Su PC sono stati corretti anche alcuni problemi con Dynamic Resolution Scaling e con impostazioni grafiche non supportate dalla GPU. Su console sono state aggiunte opzioni grafiche come Bloom, Light Shafts e Depth of Field, oltre a ottimizzazioni e correzioni ai limiti di framerate su PS5.</p>
<h2>Che cosa resta da verificare</h2>
<p>Le patch risolvono una parte delle criticità iniziali, ma l'esperienza può ancora dipendere dalla piattaforma, dalla configurazione hardware e dalla versione installata. Prima di modificare manualmente file o impostazioni avanzate, conviene aggiornare il gioco, verificare i driver grafici e consultare le note della versione usata. CD Projekt RED ha inoltre dichiarato di lavorare a un aggiornamento per Nintendo Switch 2, senza indicare in quell'annuncio una data definitiva di rilascio.</p>
<p class="av-source-reference">Fonti ufficiali: <a href="https://www.thewitcher.com/us/en/news/52085/patch-5-01-for-the-witcher-3-wild-hunt-remastered-is-live" rel="noopener noreferrer">CD Projekt RED – note della patch 5.01, 8 ottobre 2026</a>; <a href="https://steamcommunity.com/app/292030/announcements/" rel="noopener noreferrer">Steam – annunci e hotfix ufficiali del gioco</a>.</p>"""
},
611: {
 "slug": "migliori-ring-light-streamer-creator",
 "title": "Ring light per streamer e creator: dimensioni, CRI e potenza",
 "seo": {"seo_title": "Ring light: come scegliere per streaming e video",
         "seo_description": "Guida alla ring light: diametro, lumen, temperatura colore e CRI. Confronto tra Elgato Key Light Air MK.2 e NEEWER RP18B Pro.",
         "focus_keyphrase": "ring light streamer creator"},
 "mode": "append",
 "html": """<h2>Come leggere le specifiche prima dell'acquisto</h2>
<p>Il valore in lumen indica la quantità di luce emessa, ma non basta per confrontare due prodotti: contano anche la distanza dal soggetto, la diffusione e la superficie luminosa. La temperatura colore, espressa in Kelvin, permette di passare da una luce più calda a una più fredda e va regolata in modo coerente con le altre sorgenti presenti nella stanza. Il CRI indica la fedeltà con cui vengono riprodotti i colori; per video e trucco è utile cercare valori elevati, ma è opportuno confrontare anche il TLCI quando il produttore lo dichiara.</p>
<p>Due esempi mostrano perché un pannello e una ring light non sono perfettamente intercambiabili. Elgato Key Light Air MK.2 è un pannello LED da scrivania, con luminosità fino a 2.100 lumen, intervallo 2.900–7.000 K e CRI superiore a 94; la luminosità massima richiede un'alimentazione USB-C da almeno 30 W. NEEWER RP18B Pro è invece un anello da 18 pollici, 45 W, CRI 97+ e TLCI 98, con temperatura regolabile tra 2.900 e 7.000 K. I valori dichiarati dai produttori sono misurati in condizioni differenti e non costituiscono un confronto di laboratorio diretto.</p>
<p>Per una postazione fissa con spazio limitato può essere più pratico un pannello con morsetto; per tutorial beauty e riprese frontali ravvicinate un anello grande può creare una luce uniforme e riflessi circolari negli occhi. In ogni caso, orienta la sorgente leggermente sopra la linea degli occhi, evita di puntarla direttamente nello sguardo e valuta un diffusore per ridurre ombre troppo dure.</p>
<p class="av-source-reference">Fonti tecniche dei produttori: <a href="https://help.elgato.com/hc/it/articles/48851735455761-Elgato-Key-Light-Air-MK-2-Specifiche-tecniche" rel="noopener noreferrer">Elgato – specifiche Key Light Air MK.2</a>; <a href="https://eu.neewer.com/products/neewer-rp18b-pro-ring-light-kit-66603484" rel="noopener noreferrer">NEEWER – specifiche RP18B Pro</a>.</p>"""
},
505: {
 "slug": "nuance-audio-plus-occhiali-acustici-italia",
 "title": "Nuance Audio Plus: modelli, funzioni e prezzo aggiornato",
 "seo": {"seo_title": "Nuance Audio Plus: prezzo e modelli",
         "seo_description": "Nuance Audio Plus: modelli Square, Panthos e Upturn. Il sito ufficiale indica un prezzo di partenza aggiornato da 979 euro.",
         "focus_keyphrase": "Nuance Audio Plus"},
 "mode": "append",
 "html": """<h2>Prezzo aggiornato e modelli disponibili</h2>
<p>Il prezzo di 899 euro riportato al momento del lancio non coincide più con il prezzo di partenza mostrato dal sito ufficiale. Alla verifica del 16 novembre 2026, la pagina Nuance Audio Italia presenta Nuance Audio Plus a partire da 979 euro, con importo che può variare in base alla montatura e alla configurazione delle lenti. La gamma Plus comprende tre forme — Square, Panthos e Upturn — e cinque varianti colore. Prima dell'acquisto è opportuno controllare il prezzo aggiornato e prenotare una prova presso un punto vendita, perché la vestibilità e la resa audio dipendono anche dalla persona e dall'ambiente.</p>
<p>La soluzione è pensata per migliorare l'ascolto in situazioni quotidiane, ma non sostituisce una valutazione audiologica né va scelta soltanto sulla base delle caratteristiche pubblicitarie. Chi avverte una perdita uditiva dovrebbe rivolgersi a un professionista per verificare il tipo di deficit e l'idoneità del dispositivo.</p>
<p class="av-source-reference">Fonti ufficiali: <a href="https://www.nuanceaudio.com/it-it" rel="noopener noreferrer">Nuance Audio Italia – Nuance Audio Plus</a>; <a href="https://www.nuanceaudio.com/it-it/occhiali-acustici" rel="noopener noreferrer">catalogo ufficiale, modelli, varianti e prezzi</a>.</p>"""
},
499: {
 "slug": "anker-prime-100w-offerta-39-99-euro",
 "title": "Anker Prime 100W: caratteristiche e prezzo della promozione di settembre 2026",
 "seo": {"seo_title": "Anker Prime 100W: specifiche e prezzo storico",
         "seo_description": "Anker Prime 100W A2688 offre due USB-C e una USB-A. La potenza massima è 100 W su una o due porte e 89 W con tre porte attive.",
         "focus_keyphrase": "Anker Prime 100W A2688"},
 "mode": "append",
 "html": """<h2>Una precisazione importante sulla potenza simultanea</h2>
<p>La scheda ufficiale identifica il prodotto come Anker Prime Charger A2688. I 100 W rappresentano la potenza massima disponibile con una singola porta USB-C; la potenza complessiva può arrivare a 100 W anche usando due porte, mentre con tutte e tre le porte attive il limite totale dichiarato scende a 89 W. Non significa quindi che ciascuna delle tre uscite eroghi 100 W contemporaneamente. La porta USB-A arriva a 22,5 W e le due USB-C supportano profili di ricarica rapida e PPS.</p>
<p>Per sfruttare la potenza massima serve un cavo USB-C compatibile con E-Marker e un dispositivo che supporti il profilo richiesto. La velocità effettiva dipende anche dalla batteria del dispositivo, dalla temperatura e dal protocollo di ricarica. Il prezzo di 39,99 euro citato sopra è riferito alla promozione del 30 settembre 2026, non a un prezzo garantito oggi.</p>
<p class="av-source-reference">Fonti del produttore: <a href="https://www.anker.com/eu-en/products/a2688-anker-prime-charger-100w-3-ports-gan" rel="noopener noreferrer">Anker EU – Prime Charger 100W, modello A2688</a>; <a href="https://service.anker.com/product-description/a085g0000050Q24AAE" rel="noopener noreferrer">Anker Support – distribuzione della potenza tra le porte</a>.</p>"""
},
605: {
 "slug": "bluetti-elite-30-v2-pannello-solare-offerta",
 "title": "BLUETTI Elite 30 V2: caratteristiche e prezzo della promozione di ottobre 2026",
 "seo": {"seo_title": "BLUETTI Elite 30 V2: specifiche e prezzo storico",
         "seo_description": "BLUETTI Elite 30 V2 offre 288 Wh, 600 W continui, 1.500 W Power Lifting e UPS fino a 10 ms. Prezzo riferito alla promozione di ottobre.",
         "focus_keyphrase": "BLUETTI Elite 30 V2"},
 "mode": "append",
 "html": """<h2>Specifiche ufficiali e limiti d'uso</h2>
<p>La scheda europea del produttore conferma una capacità di 288 Wh, potenza nominale di 600 W e funzione Power Lifting fino a 1.500 W per carichi compatibili. Sono presenti otto uscite, una porta USB-C Power Delivery fino a 140 W e una funzione UPS con commutazione dichiarata entro 10 millisecondi. BLUETTI indica inoltre una batteria LFP con oltre 3.000 cicli e un consumo in standby di circa 4,5 W.</p>
<p>Il valore Power Lifting non equivale alla potenza continua dell'inverter: è una modalità pensata per alcuni carichi resistivi compatibili e non rende la power station adatta a qualsiasi elettrodomestico da 1.500 W. Prima di collegare un apparecchio occorre controllarne potenza di avvio, assorbimento continuo e compatibilità. Anche la funzione UPS va valutata in base al dispositivo da proteggere e non sostituisce un impianto elettrico di emergenza certificato.</p>
<p>Il prezzo del kit da 369 euro riportato nell'articolo si riferisce alla promozione del 3 ottobre 2026. Il prezzo attuale della power station e del pannello va controllato sul sito del venditore; la dotazione può cambiare in base al bundle.</p>
<p class="av-source-reference">Fonti ufficiali: <a href="https://www.bluettipower.eu/products/elite-30-v2-portable-power-station" rel="noopener noreferrer">BLUETTI EU – Elite 30 V2, specifiche e dotazione</a>; <a href="https://it.bluettipower.eu/blogs/news/ups-portatile-protezione-blackout" rel="noopener noreferrer">BLUETTI Italia – funzionamento della modalità UPS</a>.</p>"""
},
511: {
 "slug": "galaxy-s26-plus-vs-galaxy-s25-plus-quale-scegliere",
 "title": "Galaxy S26+ vs S25+: differenze tecniche e quale scegliere",
 "seo": {"seo_title": "Galaxy S26+ vs S25+: confronto e differenze",
         "seo_description": "Confronto Galaxy S26+ e S25+: display 6,7 pollici, batteria 4.900 mAh e ricarica 45 W. Differenze tra processori e generazioni software.",
         "focus_keyphrase": "Galaxy S26+ vs Galaxy S25+"},
 "mode": "append",
 "html": """<h2>Verifica delle specifiche ufficiali</h2>
<p>Le schede Samsung confermano che Galaxy S26+ mantiene un display Dynamic AMOLED 2X da 6,7 pollici con risoluzione QHD+ e refresh rate adattivo fino a 120 Hz, batteria tipica da 4.900 mAh e ricarica cablata fino al 69% in circa 30 minuti con un alimentatore da 45 W compatibile. L'alimentatore è venduto separatamente. Per il modello S25+ la capacità tipica della batteria è anch'essa di 4.900 mAh e la ricarica cablata supporta fino a 45 W.</p>
<p>La differenza più netta tra le due generazioni resta quindi la piattaforma di elaborazione: in Italia S26+ usa Exynos 2600, mentre S25+ si basa su Snapdragon 8 Elite for Galaxy. Per decidere l'acquisto conviene confrontare anche il prezzo reale, la durata degli aggiornamenti residui del modello precedente e le funzioni software che si utilizzano davvero. I dati di autonomia e ricarica sono valori di laboratorio o del produttore: possono variare in base a temperatura, caricatore, cavo e uso simultaneo del dispositivo.</p>
<p class="av-source-reference">Fonti Samsung: <a href="https://www.samsung.com/it/smartphones/galaxy-s26/" rel="noopener noreferrer">Samsung Italia – Galaxy S26 e S26+</a>; <a href="https://news.samsung.com/it/samsung-presenta-la-serie-galaxy-s26-lo-smartphone-galaxy-ai-piu-intuitivo-di-sempre" rel="noopener noreferrer">Samsung Newsroom – specifiche della serie Galaxy S26</a>; <a href="https://www.samsung.com/it/smartphones/galaxy-s25/" rel="noopener noreferrer">Samsung Italia – gamma Galaxy S25</a>.</p>"""
},
530: {
 "slug": "redmi-note-17-pro-max-recensione",
 "title": "Redmi Note 17 Pro Max: autonomia, specifiche e prezzo aggiornato",
 "seo": {"seo_title": "Redmi Note 17 Pro Max: specifiche e prezzo",
         "seo_description": "Redmi Note 17 Pro Max offre batteria da 9.210 mAh, ricarica 100 W e display AMOLED 6,83 pollici. Prezzo e specifiche ufficiali Xiaomi Italia.",
         "focus_keyphrase": "Redmi Note 17 Pro Max 5G"},
 "mode": "append",
 "html": """<h2>Correzione delle specifiche per il mercato italiano</h2>
<p>La scheda Xiaomi Italia indica per la versione destinata al nostro mercato una protezione IP66/IP68. Il riferimento IP69K presente nella prima stesura non è riportato nella scheda italiana e viene quindi corretto: le certificazioni possono variare per Paese e variante, perciò è importante fare riferimento alla pagina del modello venduto in Italia. Xiaomi dichiara inoltre una batteria al silicio-carbonio da 9.210 mAh, ricarica HyperCharge fino a 100 W, display AMOLED da 6,83 pollici con risoluzione 1.5K e refresh rate fino a 120 Hz, processore Snapdragon 6 Gen 5, fotocamera principale da 50 MP con OIS e ultra-grandangolare da 8 MP.</p>
<p>La pagina di acquisto Xiaomi Italia mostra, alla verifica del 16 novembre 2026, un prezzo di partenza di 549,90 euro, con prezzo consigliato indicato a 699,90 euro. Il prezzo può cambiare in base alla memoria, al colore, alle promozioni e alla disponibilità; non va confuso con i prezzi di lancio riportati nella prima parte dell'articolo. Xiaomi specifica inoltre che l'alimentatore non è incluso nella confezione e che per raggiungere la potenza massima serve un caricatore compatibile.</p>
<p class="av-source-reference">Fonti ufficiali: <a href="https://www.mi.com/it/product/redmi-note-17-pro-max-5g/" rel="noopener noreferrer">Xiaomi Italia – pagina prodotto</a>; <a href="https://www.mi.com/it/product/redmi-note-17-pro-max-5g/specs/" rel="noopener noreferrer">Xiaomi Italia – specifiche tecniche</a>; <a href="https://www.mi.com/it/product/redmi-note-17-pro-max-5g/buy/" rel="noopener noreferrer">Xiaomi Italia – prezzo e disponibilità</a>.</p>"""
},
744: {
 "slug": "account-playstation-a-rischio-hacker-come-proteggersi",
 "title": "Account PlayStation: passkey, phishing e consigli per proteggersi",
 "seo": {"seo_title": "Account PlayStation: passkey e sicurezza",
         "seo_description": "Come proteggere l'account PlayStation e recuperarlo in caso di accesso sospetto: passkey, verifica in due passaggi e controllo delle sessioni.",
         "focus_keyphrase": "sicurezza account PlayStation"},
 "mode": "append",
 "html": """<h2>Se sospetti un accesso non autorizzato</h2>
<p>Se ricevi un avviso di accesso o modifica che non riconosci, non aprire i collegamenti contenuti nel messaggio. Accedi digitando direttamente l'indirizzo PlayStation o usando l'app ufficiale, controlla i metodi di accesso disponibili e cambia la password se ritieni che sia stata esposta. Proteggi anche la casella e-mail associata, perché chi controlla quell'indirizzo potrebbe tentare di reimpostare la password dell'account. Se non riesci più ad accedere, avvia il recupero tramite il supporto ufficiale e non affidare le credenziali a servizi di recupero non verificati.</p>
<p>Una buona abitudine è controllare periodicamente le impostazioni di sicurezza, conservare i codici di backup fuori dal dispositivo e usare una password diversa da quella degli altri servizi. Le funzioni e i nomi delle voci possono cambiare con gli aggiornamenti della piattaforma: fai sempre riferimento alla guida ufficiale più recente.</p>
<p class="av-source-reference">Fonte: <a href="https://www.playstation.com/it-it/support/account/security-best-practice/" rel="noopener noreferrer">PlayStation – buone pratiche di sicurezza e protezione dell'account</a>.</p>"""
},
810: {
 "slug": "vulnerabilita-jira-confluence-atlassian",
 "title": "CVE-2026-21589: patch e mitigazioni per Jira e Confluence Data Center",
 "seo": {"seo_title": "CVE-2026-21589: patch per Jira e Confluence",
         "seo_description": "Checklist per amministratori Jira e Confluence Data Center: verifica versione, applica patch, limita l'accesso e controlla i log.",
         "focus_keyphrase": "patch CVE-2026-21589 Jira Confluence"},
 "mode": "append",
 "html": """<h2>Controllo finale dopo l'aggiornamento</h2>
<p>Al termine dell'intervento registra le versioni effettive di ogni nodo, conserva il log dell'aggiornamento e verifica che il servizio sia tornato operativo. Controlla che le regole temporanee del proxy o del WAF non blocchino funzioni legittime e che non siano rimaste istanze di test o ambienti secondari esposti con versioni vulnerabili. Se i log mostrano richieste anomale, conserva le evidenze prima di ruotare o cancellare i registri e coinvolgi il responsabile della sicurezza.</p>
<p>La presenza della patch non equivale a una verifica di compromissione: l'analisi degli accessi precedenti all'aggiornamento resta un passaggio separato. Per la matrice completa dei prodotti e delle versioni corrette fa fede l'advisory del produttore, che può essere aggiornato nel tempo.</p>
<p class="av-source-reference">Riferimento: <a href="https://confluence.atlassian.com/security/cve-2026-21589-arbitrary-file-access-vulnerability-impacts-multiple-products-1870495748.html" rel="noopener noreferrer">Atlassian – advisory e istruzioni aggiornate per CVE-2026-21589</a>.</p>"""
},
900: {
 "slug": "edward-dubrovsky-arrestato-shinyhunters",
 "title": "Edward Dubrovsky arrestato: le accuse e il caso ShinyHunters",
 "seo": {"seo_title": "Edward Dubrovsky: arresto e accuse ShinyHunters",
         "seo_description": "Le ricostruzioni di Reuters e KrebsOnSecurity sull'arresto in Pennsylvania e sulle accuse nel contesto dell'indagine ShinyHunters.",
         "focus_keyphrase": "Edward Dubrovsky ShinyHunters"},
 "mode": "append",
 "html": """<h2>Quali elementi non sono ancora pubblici</h2>
<p>Le fonti consultate descrivono l'arresto e le accuse iniziali, ma non forniscono un quadro completo di tutte le prove raccolte dagli investigatori né del ruolo attribuito all'indagato in ogni singola operazione. Alcuni atti risultavano secretati o parzialmente oscurati. Per questo motivo non è corretto dedurre la responsabilità per specifiche violazioni soltanto dalla relazione investigativa con il gruppo, né presentare come accertate le ricostruzioni diffuse online. Gli sviluppi processuali vanno verificati su documenti giudiziari successivi e comunicazioni delle autorità.</p>
<p class="av-source-reference">Fonti: <a href="https://www.reuters.com/legal/government/canadian-ransomware-negotiator-arrested-amid-fbi-hacker-crackdown-2026-10-11/" rel="noopener noreferrer">Reuters – resoconto dell'11 ottobre 2026</a>; <a href="https://krebsonsecurity.com/2026/10/fbi-arrests-founder-of-ransomware-negotiation-firm/" rel="noopener noreferrer">KrebsOnSecurity – documenti giudiziari e ricostruzione dell'arresto</a>.</p>"""
},
}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "apply"])
    mode = parser.parse_args().mode
    base = os.getenv("WP_BASE_URL", "").rstrip("/").removesuffix("/wp-json")
    user = os.getenv("WP_USERNAME", "")
    password = os.getenv("WP_APP_PASSWORD", "")
    if base != BASE or not user or not password:
        raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    session = requests.Session()
    session.auth = (user, password)
    session.headers["User-Agent"] = "AIVision-Short-Article-Quality-Repair/1.0"

    def read(post_id: int) -> dict:
        response = session.get(f"{BASE}/wp-json/wp/v2/posts/{post_id}",
                               params={"context": "edit"}, timeout=(8, 35))
        response.raise_for_status()
        return response.json()

    if mode == "prepare":
        changes = []
        for post_id, spec in UPDATES.items():
            post = read(post_id)
            if post.get("status") != "publish" or post.get("slug") != spec["slug"]:
                raise RuntimeError(f"Post {post_id}: stato o slug inatteso.")
            raw = (post.get("content") or {}).get("raw")
            seo = post.get("aivision_seo")
            if not isinstance(raw, str) or not isinstance(seo, dict):
                raise RuntimeError(f"Post {post_id}: contenuto o SEO non leggibile.")
            if MARKER in raw:
                print(f"Post {post_id}: aggiornamento già presente, salto.")
                continue
            after_content = spec["html"] if spec["mode"] == "replace" else raw + "\n" + MARKER + "\n" + spec["html"]
            after_content, _ = clean_source_links(after_content)
            if spec["mode"] == "replace":
                after_content = MARKER + "\n" + after_content
            if post_id == 518:
                after_content = after_content.replace(
                    "viene proposta a 35,99 euro rispetto al prezzo di listino di 74,99 euro, con un risparmio segnalato fino al 52%",
                    "è stata proposta al lancio a 35,99 euro rispetto al prezzo di listino di 74,99 euro; la promozione è terminata il 12 ottobre 2026"
                )
                after_content = after_content.replace(
                    "mentre il prossimo anno arriverà sul mercato anche la variante Fire TV Stick Plus in alluminio e con tasti retroilluminati.",
                    ""
                )
                after_content = '<!-- ai-vision-price-status:v1 --><div class="av-price-status-note" role="note"><p><strong>Nota su prezzi e disponibilità:</strong> il prezzo di 35,99 euro era una promozione di lancio valida fino al 12 ottobre 2026. L\'offerta è terminata e il prezzo attuale va verificato presso il venditore.</p></div>\n' + after_content
            if post_id == 530:
                after_content = after_content.replace("IP69K", "IP66/IP68")
            after_seo = dict(seo)
            after_seo.update(spec["seo"])
            changes.append({
                "id": post_id, "slug": spec["slug"], "modified": post.get("modified"),
                "before_title": (post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered"),
                "after_title": spec["title"], "before_content": raw, "after_content": after_content,
                "before_seo": seo, "after_seo": after_seo,
                "before_words": len(raw.split()), "after_words": len(after_content.split())
            })
        payload = {"site": BASE, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "planned_updates": len(changes), "changes": changes}
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        BACKUP.write_text(json.dumps({
            "site": BASE, "created_at": payload["created_at"],
            "posts": [{"id": x["id"], "slug": x["slug"], "modified": x["modified"],
                       "title": x["before_title"], "content_raw": x["before_content"],
                       "aivision_seo": x["before_seo"]} for x in changes]
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Articoli brevi pianificati:", len(changes))
        return 0

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("site") != BASE or not isinstance(plan.get("changes"), list):
        raise RuntimeError("Piano non valido.")
    results, errors = [], []
    for row in plan["changes"]:
        try:
            live = read(row["id"])
            live_raw = (live.get("content") or {}).get("raw")
            live_title = (live.get("title") or {}).get("raw") or (live.get("title") or {}).get("rendered")
            if (live.get("status") != "publish" or live.get("slug") != row["slug"]
                    or live.get("modified") != row["modified"] or live_raw != row["before_content"]
                    or live_title != row["before_title"] or live.get("aivision_seo") != row["before_seo"]):
                raise RuntimeError("Articolo modificato dopo il backup: salto per evitare sovrascritture.")
            response = session.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",
                                    params={"context": "edit"},
                                    json={"title": row["after_title"], "content": row["after_content"],
                                          "aivision_seo": row["after_seo"]},
                                    timeout=(8, 45), allow_redirects=False)
            seo_status = "saved"
            if not response.ok:
                fallback = session.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",
                                        params={"context": "edit"},
                                        json={"title": row["after_title"], "content": row["after_content"]},
                                        timeout=(8, 45), allow_redirects=False)
                fallback.raise_for_status()
                seo_status = "not_saved: " + response.text[:500]
            saved = read(row["id"])
            saved_title = (saved.get("title") or {}).get("raw") or (saved.get("title") or {}).get("rendered")
            if saved_title != row["after_title"] or (saved.get("content") or {}).get("raw") != row["after_content"]:
                raise RuntimeError("Verifica titolo o contenuto fallita.")
            if seo_status == "saved":
                saved_seo = saved.get("aivision_seo") or {}
                if any(saved_seo.get(k) != v for k, v in row["after_seo"].items()):
                    seo_status = "warning: SEO non confermato dal bridge"
            results.append({"id": row["id"], "slug": row["slug"], "status": "updated_and_verified",
                            "seo_status": seo_status, "before_words": row["before_words"],
                            "after_words": row["after_words"], "title": row["after_title"]})
            print(f"Post {row['id']}: aggiornato e verificato ({seo_status}), {row['before_words']} -> {row['after_words']} parole.")
        except Exception as exc:
            errors.append({"id": row["id"], "slug": row["slug"], "status": "error", "error": str(exc)})
            print(f"Post {row['id']}: ERRORE: {exc}")
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps({"completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                  "updated": len(results), "errors": errors, "results": results},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print("Aggiornati:", len(results), "errori:", len(errors))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
