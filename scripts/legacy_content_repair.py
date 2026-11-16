#!/usr/bin/env python3
"""Riparazioni conservative dei contenuti legacy AI Vision.

- aggiunge una nota trasparente ai vecchi articoli commerciali;
- rimuove titoli che promettono prove/recensioni non svolte da AI Vision;
- riscrive alcune schede che seguivano troppo da vicino la struttura di testate terze;
- crea copertine locali per le riscritture, senza riutilizzare immagini di fonte;
- conserva backup integrali e verifica ogni aggiornamento WordPress.

Senza --apply il programma produce soltanto un piano e non scrive su WordPress.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import requests

from editorial_content_audit import analyze_post
from wp_publisher import WordPressClient, fallback_png, slugify

BASE_URL = os.getenv("WP_BASE_URL", "https://aivision.altervista.org").rstrip("/")
OUTPUT = Path("data/legacy_content_repair_backup.json")
NOTICE_MARKER = 'class="av-price-status-note"'
REPAIR_MARKER = "<!-- ai-vision-legacy-editorial-repair:v1 -->"
TIMEOUT = 30
MAX_UPDATES = 100

MONTHS_IT = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
)

APPLE_URL = "https://www.apple.com/it/iphone/compare/?modelList=iphone-18-pro%2Ciphone-18-pro-max"
SONY_URL = "https://www.sony.it/electronics/support/wireless-headphones-bluetooth-headphones/wh-ch730n/specifications"
SONY_REVIEW_URL = "https://www.tomshw.it/smartphone/recensione-sony-wh-ch730n-qualita-audio-comfort-e-tanta-autonomia"
PHILIPS_REVIEW_URL = "https://www.dday.it/redazione/58977/recensione-tv-philips-oled911-un-nuovo-campione-di-brillantezza"
ANKER_URL = "https://www.anker.com/uk/products/a110r-qi2-maggo-2-pro-magnetic-power-bank"
ANKER_REVIEW_URL = "https://www.hwupgrade.it/news/telefonia/recensione-anker-maggo-power-bank-2-pro-il-power-bank-magnetico-che-non-teme-il-calore_161829.html"
WELL_DWELLER_URL = "https://store.steampowered.com/app/3699590"
WELL_DWELLER_REVIEW_URL = "https://www.siliconera.com/review-well-dweller-is-as-charming-as-islets-and-crypt-custodian/"
QUATTRORUOTE_URL = "https://www.quattroruote.it/news/eventi/2026/10/01/quattroruote_ottobre_2026.html"


def italian_date(value: str) -> str:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return f"{parsed.day} {MONTHS_IT[parsed.month - 1]} {parsed.year}"
    except (ValueError, TypeError):
        return str(value or "data di pubblicazione")


def price_notice(published: str) -> str:
    date_label = italian_date(published)
    return (
        '<!-- ai-vision-price-status:v1 -->'
        '<div class="av-price-status-note" role="note">'
        '<p><strong>Nota su prezzi e disponibilità:</strong> i prezzi, gli sconti e le condizioni '
        f'commerciali riportati in questa pagina si riferiscono a quanto segnalato il {date_label}. '
        'Promozioni e disponibilità possono essere cambiate: verifica sempre prezzo e condizioni '
        'aggiornate sul sito del venditore prima dell’acquisto.</p></div>'
    )


WELL_DWELLER_BODY = f"""<p><strong>Well Dweller</strong> è un metroidvania fiabesco dalle tinte oscure sviluppato da Kyle Thompson, autore di <em>Islets</em> e <em>Crypt Custodian</em>. Il giocatore guida Glimmer, un piccolo uccello che usa un fiammifero per esplorare un regno ostile, affrontare creature e cercare di salvare la propria famiglia. La scheda Steam riporta l’uscita PC del 22 settembre 2026; la recensione di Siliconera elenca anche versioni per console.</p>
<h2>Esplorazione, abilità e combattimenti</h2>
<p>La struttura è quella tipica del genere: una mappa da esplorare progressivamente, percorsi che si aprono dopo aver acquisito nuove capacità e aree secondarie che premiano chi torna sui propri passi. Il fiammifero non è soltanto un elemento narrativo: serve a illuminare gli ambienti e diventa uno strumento di combattimento. Durante l’avventura si sbloccano altre abilità utili per superare ostacoli, raggiungere piattaforme e affrontare i boss.</p>
<p>L'ambientazione punta su un contrasto preciso: personaggi dall'aspetto tenero si muovono in un regno decadente, governato da una regina crudele. La storia procede attraverso incontri, dialoghi e segreti da scoprire, senza trasformare l'esplorazione in una semplice successione di combattimenti. La varietà delle aree e la ricerca di oggetti nascosti sono parte importante del ritmo.</p>
<h2>Accessibilità e lingua</h2>
<p>La recensione di Siliconera descrive un sistema di combattimento leggibile anche per chi non cerca una sfida punitiva: la fiamma portata da Glimmer funziona come indicatore visivo dello stato di salute, mentre gli attacchi dei nemici vengono anticipati da segnali riconoscibili. Il platforming del percorso principale è considerato accessibile; la ricerca dei segreti e alcune sezioni opzionali possono invece richiedere più precisione.</p>
<p>Un elemento meno immediato è la guarigione. Secondo la prova di Siliconera, non basta attivare un comando: bisogna fermare un indicatore nel punto corretto. La meccanica aggiunge tensione agli scontri, ma può diventare frustrante nelle fasi avanzate, soprattutto contro i boss.</p>
<h2>A chi può interessare</h2>
<p>Well Dweller può interessare a chi apprezza i metroidvania disegnati a mano, le ambientazioni dark fantasy e le avventure con una componente narrativa marcata. Siliconera riferisce di aver completato la versione Switch 2 in circa nove ore: è il tempo di quella specifica partita, non una durata garantita per tutti. La stessa testata segnala versioni per Switch, Switch 2, PS5, Xbox One, Xbox Series X e PC; disponibilità e lingue possono variare a seconda dello store e della regione.</p>
<p>Questa scheda riassume la descrizione ufficiale del gioco e le osservazioni della recensione collegata; AI Vision non ha effettuato una prova diretta. Prima dell'acquisto conviene controllare sulla piattaforma scelta le lingue disponibili, eventuali demo e i requisiti aggiornati.</p>
<p class="av-source-reference">Fonti: <a href="{WELL_DWELLER_URL}" rel="noopener noreferrer">scheda ufficiale Well Dweller su Steam</a>; <a href="{WELL_DWELLER_REVIEW_URL}" rel="noopener noreferrer">recensione di Siliconera</a>.</p>
{REPAIR_MARKER}"""

SONY_BODY = f"""<p>Le <strong>Sony WH-CH730N</strong> sono cuffie wireless over-ear con cancellazione attiva del rumore, progettate per l'ascolto quotidiano, il lavoro e gli spostamenti. Il dato che spicca nella scheda tecnica è l'autonomia dichiarata: fino a 50 ore con la cancellazione del rumore attiva e fino a 75 ore con NC disattivata. Sony indica inoltre un peso di circa 207 grammi, driver dinamici da 30 mm e connessione multipoint.</p>
<h2>Autonomia e caratteristiche ufficiali</h2>
<p>La batteria è dichiarata per un massimo di 50 ore di riproduzione musicale con NC attiva e 75 ore senza cancellazione. Per le chiamate continue, i valori indicati sono fino a 35 ore con NC e 40 ore senza. La ricarica completa richiede circa tre ore tramite USB. Sono valori del produttore, non misurazioni effettuate da AI Vision: il risultato reale dipende da volume, codec, connessioni e funzioni utilizzate.</p>
<p>La dotazione comprende Bluetooth, connessione a due dispositivi, ingresso mini-jack e modalità Suono ambiente. L'app Sony Sound Connect consente di intervenire sulle impostazioni audio e regolare il livello di trasparenza ambientale. I driver da 30 mm e il peso contenuto collocano il prodotto nella fascia delle cuffie da usare per molte ore, più che in quella dei modelli pensati per l'ascolto audiofilo.</p>
<h2>Come si comporta la cancellazione del rumore</h2>
<p>La cancellazione attiva è utile soprattutto contro rumori costanti, come il ronzio di un ambiente di lavoro o il rumore regolare dei mezzi pubblici. Non va però confusa con l'isolamento dei modelli premium: voci vicine e suoni improvvisi possono rimanere percepibili. Nella prova pubblicata da Tom's Hardware Italia, l'ANC è stata giudicata adeguata alla fascia di prezzo, ma meno efficace sulle conversazioni e sui rumori non continui.</p>
<p>La stessa prova segnala un'impostazione sonora piuttosto calda e un comfort generalmente buono, con un limite pratico legato ai cuscinetti che possono trattenere calore durante sessioni prolungate. Sono impressioni del recensore di Tom's Hardware, non risultati di un test svolto da AI Vision.</p>
<h2>Per chi hanno senso</h2>
<p>Le WH-CH730N sono interessanti per chi mette al primo posto autonomia, peso contenuto e funzioni quotidiane come multipoint e modalità ambiente. Sono meno adatte a chi cerca la cancellazione più efficace possibile, materiali premium o una certificazione per sport e pioggia: Sony non indica una protezione specifica contro acqua e sudore.</p>
<p>Prima dell'acquisto conviene confrontare il prezzo del momento con quello delle cuffie della generazione precedente e con le alternative della stessa fascia. Il listino e le offerte cambiano spesso; la valutazione di Tom's Hardware del 28 ottobre 2026 riportava prezzi online inferiori ai 100 euro, ma non è una quotazione garantita oggi.</p>
<p class="av-source-reference">Fonti: <a href="{SONY_URL}" rel="noopener noreferrer">specifiche ufficiali Sony</a>; <a href="{SONY_REVIEW_URL}" rel="noopener noreferrer">prova di Tom's Hardware Italia</a>. AI Vision non ha effettuato una prova diretta del prodotto.</p>
{REPAIR_MARKER}"""

PHILIPS_BODY = f"""<p>Il <strong>Philips OLED+911</strong> punta su tre elementi: un pannello OLED di nuova generazione, l'elaborazione video Philips con Ambilight e un sistema audio sviluppato con Bowers &amp; Wilkins. Il dato più appariscente emerso dalle misurazioni pubblicate da DDay.it è un picco superiore a 4.200 cd/m², ma va letto nel contesto corretto: si tratta di una piccola porzione dello schermo e di un risultato raggiunto per intervalli brevi con la funzione di incremento della luminosità attiva.</p>
<h2>Il picco di luminosità va interpretato</h2>
<p>La misura riportata da DDay supera i 4.200 cd/m² su una finestra del 2% e scende a circa 3.500 cd/m² al 5%. Non significa che l'intero pannello possa mantenere quella luminosità su immagini estese o per tutta la durata di un film. È un valore di picco utile per riprodurre riflessi e dettagli HDR molto intensi, ma la resa complessiva dipende anche da gestione dei toni, accuratezza del colore e comportamento nelle scene più ampie.</p>
<p>Per questo è più utile considerare il risultato insieme alle altre caratteristiche del televisore, anziché fermarsi al numero più alto. Le misure citate sono quelle della prova di DDay.it: AI Vision non ha eseguito misurazioni di laboratorio sul modello.</p>
<h2>Ambilight e passaggio a Titan OS</h2>
<p>Ambilight resta uno degli elementi distintivi della proposta Philips: l'illuminazione sul retro del televisore estende i colori della scena sulla parete e può rendere più coinvolgente la visione in ambienti poco illuminati. La novità software è il passaggio da Google TV a Titan OS. La piattaforma punta a un'interfaccia snella, ma rinuncia all'ecosistema del Play Store; prima dell'acquisto è quindi opportuno controllare che le app utilizzate abitualmente siano disponibili nella propria regione.</p>
<p>DDay segnala la presenza delle principali app di streaming e l'arrivo di NOW, oltre alla compatibilità prevista con Dolby Vision 2 Max. La disponibilità effettiva delle applicazioni e degli aggiornamenti può cambiare nel tempo e va verificata con Philips.</p>
<h2>Audio Bowers &amp; Wilkins e uso quotidiano</h2>
<p>La collaborazione con Bowers &amp; Wilkins riguarda il sistema audio integrato. Nella valutazione di DDay la resa è pulita e dettagliata, mentre la gamma bassa non scende molto in profondità: chi cerca un impatto più marcato nei film potrebbe preferire l'aggiunta di un subwoofer esterno. Anche la gestione dei contenuti compressi in streaming merita attenzione, perché la qualità della sorgente incide molto su un pannello di questo livello.</p>
<h2>Per chi è pensato</h2>
<p>OLED+911 è una proposta da valutare per chi guarda molti contenuti HDR, apprezza Ambilight e vuole un comparto audio più curato rispetto a quello tipico dei televisori sottili. Il compromesso principale da valutare non è soltanto il prezzo, ma anche Titan OS: chi dipende da app particolari dovrebbe verificare la compatibilità prima di scegliere.</p>
<p>DDay riportava un prezzo di listino di 2.199 euro nella propria prova. È un riferimento editoriale, non un prezzo di vendita aggiornato: controlla sempre il listino e le offerte correnti presso i rivenditori.</p>
<p class="av-source-reference">Fonte delle misurazioni e delle impressioni: <a href="{PHILIPS_REVIEW_URL}" rel="noopener noreferrer">prova indipendente di DDay.it</a>. AI Vision non ha testato direttamente il televisore.</p>
{REPAIR_MARKER}"""

ANKER_BODY = f"""<p><strong>Anker MagGo Power Bank 2 Pro</strong> (modello A110R) è una batteria magnetica da 10.000 mAh che combina ricarica wireless Qi2.2 fino a 25 W, una porta USB-C da 45 W e un sistema di raffreddamento attivo. La ventola integrata è la caratteristica che la distingue dai power bank magnetici più semplici, ma la compatibilità dello smartphone è il primo elemento da controllare prima dell'acquisto.</p>
<h2>25 W wireless: compatibilità da verificare</h2>
<p>Anker indica una potenza wireless massima di 25 W con Qi2.2. La pagina di compatibilità Anker elenca gli iPhone delle serie 13–18, con l’eccezione di iPhone 16e. Per altri telefoni non bisogna dare per scontata la potenza massima: occorre verificare lo standard wireless effettivamente supportato. Una cover magnetica può risolvere il fissaggio al telefono, ma non rende automaticamente compatibile la ricarica Qi2.2 a 25 W.</p>
<p>La batteria può essere usata anche tramite cavo: la porta USB-C supporta fino a 45 W in ingresso e in uscita. Questo rende il dispositivo più versatile quando serve ricaricare un telefono, un tablet o la stessa power bank in tempi contenuti.</p>
<h2>Perché c'è una ventola</h2>
<p>La ricarica wireless ad alta potenza genera calore. Anker ha inserito una ventola e il sistema SnapCool per gestire la temperatura durante le sessioni più impegnative. Sono disponibili una modalità orientata al raffreddamento e una modalità silenziosa, oltre alla possibilità di disattivare la ricarica wireless. La ventola aggiunge componenti e spessore, ma consente di affrontare il problema termico senza affidarsi soltanto alla riduzione automatica della potenza.</p>
<p>Il prodotto pesa circa 220 grammi e misura 105,15 × 70,9 × 17,8 mm secondo la scheda del produttore. Integra anche un piccolo display per controllare lo stato della batteria e un supporto regolabile, utile per appoggiare il telefono durante la ricarica. La capacità nominale è di 10.000 mAh: l'energia effettivamente trasferita allo smartphone sarà inferiore, soprattutto usando la modalità wireless, a causa delle normali perdite di conversione.</p>
<h2>Quando conviene</h2>
<p>Il MagGo 2 Pro ha più senso per chi possiede un iPhone compatibile e usa spesso la ricarica magnetica. Per un telefono Android che si ferma a 15 W wireless, parte del sovrapprezzo legato a Qi2.2 potrebbe non essere sfruttato. Anche peso e dimensioni vanno considerati: è una batteria da agganciare al telefono per una ricarica comoda, non la soluzione più leggera da portare sempre in tasca.</p>
<p>Hardware Upgrade riportava un listino di 109,99 euro e una promozione a 87,99 euro il 10 novembre 2026. Il prezzo promozionale è legato a quella rilevazione e può essere cambiato: verifica la disponibilità e il prezzo correnti prima dell'acquisto.</p>
<p class="av-source-reference">Fonti: <a href="{ANKER_URL}" rel="noopener noreferrer">scheda ufficiale Anker A110R</a>; <a href="{ANKER_REVIEW_URL}" rel="noopener noreferrer">prova di Hardware Upgrade</a>. AI Vision non ha eseguito test di ricarica o misurazioni termiche sul prodotto.</p>
{REPAIR_MARKER}"""


REVIEW_REPAIRS = {
    478: {
        "title": "iPhone 18 Pro: caratteristiche, chip A20 Pro e novità fotografiche",
        "append_html": (
            '<p class="av-source-reference">Specifiche e confronto dei modelli: '
            f'<a href="{APPLE_URL}" rel="noopener noreferrer">documentazione ufficiale Apple</a>. '
            'Questa scheda riassume le caratteristiche dichiarate dal produttore e non è una prova diretta di AI Vision.</p>'
            + REPAIR_MARKER
        ),
    },
    536: {
        "title": "iPhone 18 Pro Max: specifiche, autonomia e differenze con il modello Pro",
        "append_html": (
            '<p class="av-source-reference">Specifiche e confronto dei modelli: '
            f'<a href="{APPLE_URL}" rel="noopener noreferrer">documentazione ufficiale Apple</a>. '
            'Questa scheda riassume le caratteristiche dichiarate dal produttore e non è una prova diretta di AI Vision.</p>'
            + REPAIR_MARKER
        ),
    },
    551: {
        "title": "Leapmotor B03X: autonomia WLTP, consumi e prezzi del SUV elettrico",
        "append_html": (
            '<p class="av-source-reference">Per i dati di prova su strada e i consumi reali, consulta '
            f'<a href="{QUATTRORUOTE_URL}" rel="noopener noreferrer">il test drive di Quattroruote</a>. '
            'I consumi su strada dipendono da percorso, temperatura, velocità e climatizzazione; AI Vision non ha effettuato un test drive indipendente.</p>'
            + REPAIR_MARKER
        ),
    },
    642: {
        "title": "Well Dweller: trama, gameplay e accessibilità del metroidvania di Kyle Thompson",
        "body_html": WELL_DWELLER_BODY,
        "cover_category": "Gaming e console",
        "cover_alt": "Copertina grafica AI Vision per la scheda informativa di Well Dweller",
    },
    807: {
        "title": "Sony WH-CH730N: autonomia, ANC e caratteristiche da conoscere",
        "body_html": SONY_BODY,
        "cover_category": "Tecnologia e prodotti",
        "cover_alt": "Copertina grafica AI Vision per la scheda tecnica delle Sony WH-CH730N",
    },
    858: {
        "title": "Philips OLED+911: luminosità, Ambilight e Titan OS nel nuovo televisore OLED",
        "body_html": PHILIPS_BODY,
        "cover_category": "Tecnologia e prodotti",
        "cover_alt": "Copertina grafica AI Vision per la scheda del televisore Philips OLED+911",
    },
    1753: {
        "title": "Anker MagGo Power Bank 2 Pro: Qi2.2 a 25 W, raffreddamento e compatibilità",
        "body_html": ANKER_BODY,
        "cover_category": "Accessori e postazioni",
        "cover_alt": "Copertina grafica AI Vision per la scheda Anker MagGo Power Bank 2 Pro",
    },
}


def wp_fetch_posts(client: WordPressClient) -> list[dict]:
    posts = []
    for page in range(1, 20):
        response = client.session.get(
            client._url("posts"),
            params={
                "status": "publish", "context": "edit", "per_page": 100,
                "page": page, "orderby": "id", "order": "asc",
                "_fields": "id,title,content,link,slug,date,modified,featured_media",
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        batch = response.json()
        if not isinstance(batch, list):
            raise RuntimeError(f"Risposta WordPress non valida alla pagina {page}.")
        if not batch:
            break
        posts.extend(batch)
        if len(batch) < 100:
            break
    return posts


def get_raw_title(post: dict) -> str:
    title = post.get("title") or {}
    return str(title.get("raw") or title.get("rendered") or "")


def get_raw_content(post: dict) -> str:
    content = post.get("content") or {}
    return str(content.get("raw") or content.get("rendered") or "")


def build_plan(posts: list[dict], today: dt.date | None = None) -> list[dict]:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    plan = []
    for post in posts:
        post_id = int(post.get("id") or 0)
        old_title = get_raw_title(post)
        old_content = get_raw_content(post)
        new_title = old_title
        new_content = old_content
        cover_category = ""
        cover_alt = ""

        repair = REVIEW_REPAIRS.get(post_id)
        if repair and REPAIR_MARKER not in old_content:
            new_title = repair["title"]
            if repair.get("body_html"):
                new_content = repair["body_html"]
                cover_category = repair.get("cover_category", "")
                cover_alt = repair.get("cover_alt", "")
            elif repair.get("append_html"):
                new_content = old_content.rstrip() + "\n" + repair["append_html"]

        audit_post = dict(post)
        audit_post["content"] = dict(post.get("content") or {})
        audit_post["content"]["rendered"] = str(
            (post.get("content") or {}).get("rendered") or old_content
        )
        analysis = analyze_post(audit_post, today)
        has_stale_offer = any(x["code"] == "stale_offer_review" for x in analysis["flags"])
        if has_stale_offer and NOTICE_MARKER not in new_content:
            new_content = price_notice(str(post.get("date") or "")) + "\n" + new_content

        if new_title != old_title or new_content != old_content or cover_category:
            plan.append({
                "id": post_id,
                "url": post.get("link"),
                "date": post.get("date"),
                "modified_before": post.get("modified"),
                "old_title": old_title,
                "new_title": new_title,
                "old_content": old_content,
                "new_content": new_content,
                "featured_media_before": post.get("featured_media"),
                "cover_category": cover_category,
                "cover_alt": cover_alt,
                "reasons": [
                    *(["stale_offer_notice"] if has_stale_offer and NOTICE_MARKER not in old_content else []),
                    *(["review_title_or_source_repair"] if repair and REPAIR_MARKER not in old_content else []),
                ],
            })
    return plan


def apply_plan(client: WordPressClient, plan: list[dict]) -> list[dict]:
    results = []
    for item in plan[:MAX_UPDATES]:
        post_id = item["id"]
        try:
            current_response = client.session.get(
                client._url(f"posts/{post_id}"),
                params={"context": "edit", "_fields": "id,modified,content,title,featured_media"},
                timeout=TIMEOUT,
            )
            current_response.raise_for_status()
            current = current_response.json()
            if str(current.get("modified")) != str(item.get("modified_before")):
                results.append({"id": post_id, "status": "skipped_concurrent_edit", "url": item["url"]})
                continue

            payload = {"title": item["new_title"], "content": item["new_content"]}
            if item.get("cover_category"):
                image = fallback_png(item["cover_category"])
                media = client.upload_media(
                    image,
                    f"ai-vision-legacy-{post_id}-{slugify(item['new_title'])}.png",
                    "image/png",
                    item.get("cover_alt") or item["new_title"],
                    "Copertina grafica originale AI Vision",
                )
                if not media.get("id"):
                    raise RuntimeError("Copertina grafica non caricata.")
                payload["featured_media"] = int(media["id"])

            update = client.session.post(
                client._url(f"posts/{post_id}"),
                json=payload,
                timeout=TIMEOUT,
            )
            update.raise_for_status()

            verify_response = client.session.get(
                client._url(f"posts/{post_id}"),
                params={"context": "edit", "_fields": "id,modified,content,title,featured_media"},
                timeout=TIMEOUT,
            )
            verify_response.raise_for_status()
            verified = verify_response.json()
            verified_content = get_raw_content(verified)
            verified_title = get_raw_title(verified)
            if verified_title != item["new_title"]:
                raise RuntimeError("Verifica titolo fallita.")
            if item["new_content"] not in verified_content and (
                NOTICE_MARKER not in verified_content and REPAIR_MARKER not in verified_content
            ):
                raise RuntimeError("Verifica contenuto fallita.")
            results.append({
                "id": post_id, "status": "updated", "url": item["url"],
                "title": verified_title, "featured_media": verified.get("featured_media"),
                "reasons": item["reasons"],
            })
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            results.append({"id": post_id, "status": "error", "url": item["url"], "error": str(exc)})
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="applica le modifiche su WordPress")
    args = parser.parse_args()

    username = os.getenv("WP_USERNAME", "")
    app_password = os.getenv("WP_APP_PASSWORD", "")
    if not username or not app_password:
        raise RuntimeError("WP_USERNAME e WP_APP_PASSWORD sono necessari per leggere/modificare WordPress.")

    client = WordPressClient(BASE_URL, username, app_password, dry_run=False)
    posts = wp_fetch_posts(client)
    plan = build_plan(posts)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    backup = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "site": BASE_URL,
        "mode": "apply" if args.apply else "dry_run",
        "total_posts_scanned": len(posts),
        "planned_updates": len(plan),
        "items": plan,
    }
    if args.apply:
        backup["results"] = apply_plan(client, plan)
        backup["updated"] = sum(x["status"] == "updated" for x in backup["results"])
        backup["errors"] = sum(x["status"] == "error" for x in backup["results"])
    OUTPUT.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
    print("LEGACY CONTENT REPAIR", "APPLY" if args.apply else "DRY RUN")
    print("Articoli esaminati:", len(posts))
    print("Modifiche pianificate:", len(plan))
    if args.apply:
        print("Articoli aggiornati:", backup["updated"], "errori:", backup["errors"])
    print("Backup/report:", OUTPUT)
    return 1 if args.apply and backup.get("errors", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
