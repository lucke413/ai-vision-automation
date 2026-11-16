#!/usr/bin/env python3
"""Aggiunge approfondimenti utili ai cinque articoli brevi riscritti nella prima passata."""
from __future__ import annotations
import argparse, datetime as dt, json, os
from pathlib import Path
import requests

BASE = "https://aivision.altervista.org"
PLAN = Path("data/short_article_followup_plan.json")
BACKUP = Path("data/short_article_followup_backup.json")
RESULT = Path("data/short_article_followup_result.json")
MARKER = "<!-- ai-vision-short-quality-followup:v1 -->"

UPDATES = {
557: {
 "slug": "chatgpt-virtual-try-on-prova-vestiti",
 "html": """<h2>Limiti della simulazione e consigli prima dell'acquisto</h2>
<p>La prova generata è un aiuto per visualizzare un possibile abbinamento, non una misurazione sartoriale. La resa può cambiare in base a posa, illuminazione, immagine caricata e caratteristiche del prodotto; non consente di dedurre con precisione la taglia né la vestibilità del tessuto in movimento. Per questo è preferibile usarla per confrontare colori e stili, poi controllare misure, composizione, disponibilità e condizioni di reso nella scheda del negozio.</p>
<p>Il pulsante Prova compare nelle schede di abbigliamento e accessori supportate: non è garantito che sia presente per ogni prodotto o collegamento esterno. La foto di riferimento può essere modificata o eliminata dalle impostazioni indicate da OpenAI; chi condivide un dispositivo dovrebbe verificare di non lasciare immagini personali accessibili ad altri utenti.</p>"""
},
596: {
 "slug": "fuga-d-emergenza-tesla-ricarica",
 "html": """<h2>Quando interrompere la procedura e chiedere assistenza</h2>
<p>Se il cavo non si libera dopo aver interrotto la sessione, non usare pinze, leve o altri utensili e non tentare di tirare il connettore con forza. Verifica che la presa di ricarica non mostri segnalazioni di guasto e contatta l'operatore della colonnina o l'assistenza Tesla. In presenza di odore di bruciato, calore anomalo, fumo o cavi danneggiati, allontanati dal veicolo e segui le procedure di emergenza locali.</p>
<p>La procedura descritta nel manuale Model Y non deve essere considerata una procedura universale per tutti i veicoli elettrici o per tutte le Tesla. Prima di intervenire, consulta il manuale associato al VIN e all'anno del veicolo. La sicurezza ha priorità sulla rapidità: non intervenire mai su componenti ad alta tensione e non eseguire il rilascio mentre la ricarica è attiva.</p>"""
},
572: {
 "slug": "telecamera-apple-senza-video-ia-privacy",
 "html": """<h2>Quali aspetti della privacy andrebbero verificati</h2>
<p>Se il progetto dovesse diventare un prodotto commerciale, le informazioni più importanti da valutare non sarebbero soltanto la risoluzione del sensore o il prezzo. Servirebbe sapere quali eventi vengono analizzati, se l'elaborazione avviene sul dispositivo o nel cloud, quali descrizioni vengono conservate, per quanto tempo e chi può consultarle. Anche un sistema che non salva video potrebbe trattare dati personali attraverso riconoscimento di persone, orari di presenza e notifiche contestuali.</p>
<p>Per ora questi dettagli non sono stati confermati da Apple. Chi desidera installare oggi una telecamera domestica dovrebbe quindi basarsi sulle funzioni documentate dei prodotti disponibili, controllare le aree riprese, le autorizzazioni degli utenti e le opzioni di conservazione dei filmati, senza acquistare in previsione di un dispositivo non annunciato.</p>"""
},
542: {
 "slug": "circuito-europeo-pagamenti-enp",
 "html": """<h2>Cosa cambia, in pratica, per consumatori ed esercenti</h2>
<p>Per i consumatori l'obiettivo è poter inviare denaro oltre confine usando l'app nazionale già installata, senza dover aprire necessariamente un nuovo conto o imparare un sistema diverso. Questo risultato dipende però dall'interoperabilità tecnica, dalle banche aderenti e dai Paesi attivati nella singola fase. La platea potenziale di 130 milioni di utenti non significa che ogni utente possa già pagare in tutti i negozi dei 14 Paesi.</p>
<p>Per gli esercenti l'arrivo dei pagamenti online e POS richiederà l'adesione dei fornitori di servizi di pagamento e l'aggiornamento dei sistemi di incasso. ENP non ha ancora pubblicato un tariffario generale che permetta di confrontare le commissioni con quelle delle carte: i costi dipenderanno dai servizi e dai contratti applicati dai singoli operatori. La rete va quindi seguita come infrastruttura in costruzione, non come alternativa immediatamente disponibile in ogni punto vendita.</p>"""
},
545: {
 "slug": "the-witcher-3-remastered-problemi-performance-soluzioni",
 "html": """<h2>Come verificare di avere la versione aggiornata</h2>
<p>Su PC controlla la versione installata nel launcher utilizzato (Steam, GOG, Epic Games Store o Battle.net) e lascia completare il download della patch prima di avviare il gioco. Se persistono problemi grafici, verifica che i driver della scheda video siano aggiornati e ripristina le impostazioni che non sono supportate dalla GPU. Evita di modificare manualmente i file di configurazione prima di aver verificato se il problema è già stato corretto da una patch.</p>
<p>Su PlayStation 5 e Xbox Series X|S la disponibilità dell'aggiornamento dipende dalla versione distribuita per la console e dalla regione. Se un problema continua dopo l'installazione della 5.01, segnala piattaforma, versione del gioco e passaggi che riproducono l'errore nei canali di supporto ufficiali. Questo aiuta a distinguere un bug del gioco da un problema locale di configurazione.</p>"""
}
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
    session.headers["User-Agent"] = "AIVision-Short-Article-Followup/1.0"

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
            if not isinstance(raw, str):
                raise RuntimeError(f"Post {post_id}: contenuto non leggibile.")
            if MARKER in raw:
                print(f"Post {post_id}: approfondimento già presente, salto.")
                continue
            after = raw + "\n" + MARKER + "\n" + spec["html"]
            changes.append({"id": post_id, "slug": spec["slug"], "modified": post.get("modified"),
                            "title": (post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered"),
                            "before_content": raw, "after_content": after,
                            "before_words": len(raw.split()), "after_words": len(after.split())})
        payload = {"site": BASE, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "planned_updates": len(changes), "changes": changes}
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        BACKUP.write_text(json.dumps({"site": BASE, "created_at": payload["created_at"],
            "posts": [{"id": x["id"], "slug": x["slug"], "modified": x["modified"],
                       "title": x["title"], "content_raw": x["before_content"]} for x in changes]},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print("Approfondimenti pianificati:", len(changes))
        return 0

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    results, errors = [], []
    for row in plan["changes"]:
        try:
            live = read(row["id"])
            live_raw = (live.get("content") or {}).get("raw")
            live_title = (live.get("title") or {}).get("raw") or (live.get("title") or {}).get("rendered")
            if (live.get("status") != "publish" or live.get("slug") != row["slug"]
                    or live.get("modified") != row["modified"] or live_raw != row["before_content"]
                    or live_title != row["title"]):
                raise RuntimeError("Articolo modificato dopo il backup; salto.")
            response = session.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",
                                    params={"context": "edit"}, json={"content": row["after_content"]},
                                    timeout=(8, 45), allow_redirects=False)
            response.raise_for_status()
            saved = read(row["id"])
            if (saved.get("content") or {}).get("raw") != row["after_content"]:
                raise RuntimeError("Verifica contenuto fallita.")
            results.append({"id": row["id"], "status": "updated_and_verified",
                            "before_words": row["before_words"], "after_words": row["after_words"]})
            print(f"Post {row['id']}: approfondimento verificato, {row['before_words']} -> {row['after_words']} parole.")
        except Exception as exc:
            errors.append({"id": row["id"], "status": "error", "error": str(exc)})
            print(f"Post {row['id']}: ERRORE: {exc}")
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps({"completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                  "updated": len(results), "errors": errors, "results": results},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print("Approfonditi:", len(results), "errori:", len(errors))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
