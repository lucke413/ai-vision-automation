#!/usr/bin/env python3
"""Aggiorna articoli di sicurezza con verifiche ufficiali, backup e controllo post-scrittura.
Trigger operativo 16 novembre 2026."""
from __future__ import annotations
import argparse, datetime as dt, json, os
from pathlib import Path
from public_source_links import clean_source_links

import requests

BASE = "https://aivision.altervista.org"
PLAN = Path("data/security_article_update_plan.json")
BACKUP = Path("data/security_article_update_backup.json")
RESULT = Path("data/security_article_update_result.json")
MARKER = "<!-- ai-vision-security-update:v1 -->"

UPDATES = {
502: {
    "slug": "samsung-galaxy-tab-s12-ultra-e-s12-plus-specifiche-prezzi",
    "title": "Samsung Galaxy Tab S12 Ultra e S12+: specifiche, AI e supporto software",
    "seo": {"seo_title": "Galaxy Tab S12 Ultra e S12+: supporto e specifiche",
            "seo_description": "Galaxy Tab S12 Ultra e S12+ offrono fino a sette aggiornamenti OS e sicurezza. Specifiche e durata del supporto dichiarata da Samsung.",
            "focus_keyphrase": "Samsung Galaxy Tab S12 Ultra S12+"},
    "mode": "append",
    "html": """<h2>Supporto software e aggiornamenti di sicurezza</h2>
<p>Oltre alle specifiche hardware, per un tablet di questa fascia è importante valutare la durata del supporto. Samsung dichiara per Galaxy Tab S12 Ultra e Galaxy Tab S12+ fino a sette generazioni di aggiornamenti del sistema operativo e della sicurezza. Per il modello Galaxy Tab S12 Ultra, la scheda prodotto Samsung indica il periodo degli aggiornamenti di sicurezza fino al 30 settembre 2033. La data va comunque verificata sulla pagina del modello e della variante effettivamente acquistata: disponibilità e politiche di supporto possono differire per mercato e configurazione.</p>
<p>Il numero di aggiornamenti promessi non significa che ogni funzione Galaxy AI resti identica nel tempo: alcune funzioni possono dipendere dalla versione di One UI, dal Paese, dalla lingua e dai servizi di terze parti. Per questo è utile distinguere il supporto di sicurezza, che protegge il dispositivo, dalla disponibilità delle singole funzioni software.</p>
<p class="av-source-reference">Fonti ufficiali: <a href="https://www.samsung.com/it/tablets/galaxy-tab-s/galaxy-tab-s12-ultra-gray-512gb-sm-x940nzapeub/" rel="noopener noreferrer">scheda Samsung Galaxy Tab S12 Ultra e periodo di aggiornamento</a>; <a href="https://news.samsung.com/global/samsung-introduces-galaxy-tab-s12-series-the-ultimate-productivity-powerhouse-built-for-growth" rel="noopener noreferrer">Samsung Newsroom: Galaxy Tab S12 Series e supporto software</a>.</p>"""
},
560: {
    "slug": "vulnerabilita-fortimail-attacchi-zero-day",
    "title": "FortiMail CVE-2026-104286: patch correttive e versioni vulnerabili",
    "seo": {"seo_title": "FortiMail CVE-2026-104286: patch e versioni corrette",
            "seo_description": "CVE-2026-104286 è sfruttata attivamente su FortiMail. Versioni corrette, workaround e verifiche da eseguire sugli apparati esposti.",
            "focus_keyphrase": "CVE-2026-104286 FortiMail"},
    "mode": "append",
    "html": """<h2>Aggiornamento del 16 novembre 2026: versioni correttive</h2>
<p>Le indicazioni pubblicate dopo la prima segnalazione precisano le versioni correttive da verificare con attenzione. Il Canadian Centre for Cyber Security riporta FortiMail 7.4.9, 7.6.7 e 8.0.2 come versioni corrette per i rispettivi rami; per gli apparati sul ramo 7.2 indica la necessità di passare al ramo 7.4 o successivo. Prima di pianificare l'aggiornamento, gli amministratori devono consultare l'avviso Fortinet PSIRT FG-IR-26-175 e verificare la matrice ufficiale per la propria build: non bisogna dedurre che una versione sia sicura soltanto dal numero principale.</p>
<p>La Cyber Security Agency di Singapore ha segnalato lo sfruttamento attivo della vulnerabilità. Fra le misure temporanee indicate dalle autorità e dal produttore figurano la disattivazione della funzionalità IBE quando applicabile e la limitazione dell'accesso all'interfaccia di gestione alle reti fidate. Dopo l'aggiornamento è opportuno controllare gli indicatori di compromissione e i log: una patch installata non dimostra, da sola, che un apparato non sia stato compromesso in precedenza.</p>
<p class="av-source-reference">Fonti tecniche: <a href="https://fortiguard.fortinet.com/psirt/FG-IR-26-175" rel="noopener noreferrer">Fortinet PSIRT FG-IR-26-175</a>; <a href="https://www.csa.gov.sg/alerts-and-advisories/alerts/al-2026-133/" rel="noopener noreferrer">Cyber Security Agency of Singapore – avviso su FortiMail</a>; <a href="https://www.cyber.gc.ca/en/alerts-advisories/fortinet-security-advisory-av26-989" rel="noopener noreferrer">Canadian Centre for Cyber Security – versioni e aggiornamenti</a>.</p>"""
},
687: {
    "slug": "universita-tecnica-danimarca-violazione-dati",
    "title": "Violazione DTU: fino a 200.000 utenti potenzialmente coinvolti",
    "seo": {"seo_title": "Violazione DTU: fino a 200.000 utenti coinvolti",
            "seo_description": "La DTU aggiorna la timeline dell'attacco a DTUBasen: possibili profili ospiti coinvolti, dati dal 2003 e consigli ufficiali agli utenti.",
            "focus_keyphrase": "violazione dati DTU"},
    "mode": "append",
    "html": """<h2>Aggiornamento del 16 novembre 2026: la timeline ufficiale</h2>
<p>La timeline pubblicata dalla Technical University of Denmark aggiunge un elemento importante rispetto al primo comunicato del 2 ottobre. Il 26 ottobre l'università ha riferito che anche i profili ospiti gestiti tramite guest.dtu.dk potrebbero essere stati coinvolti, perché il sistema si trova nello stesso ambiente di DTUBasen. Secondo la stessa timeline, le informazioni potenzialmente interessate in questi profili ospiti non includono i numeri CPR.</p>
<p>La ricostruzione dell'ateneo indica che l'attacco è iniziato il 15 settembre 2026 con la compromissione di un account esterno di tipo guest, privo di diritti generali nell'università. L'attore ha poi sondato il sistema di gestione delle identità e, durante una procedura di reimpostazione password, sarebbe riuscito a intercettare credenziali. Il 7 ottobre DTU ha avviato un reset obbligatorio delle password degli utenti attivi; il 9 ottobre ha completato il reset delle password non modificate entro la scadenza.</p>
<p>Resta fondamentale la distinzione fra il numero di profili presenti nel sistema e il numero di persone effettivamente colpite: DTU parla di informazioni relative a un massimo di 200.000 utenti attuali ed ex utenti, ma dichiara di non poter stabilire con precisione quante persone siano state interessate né quali dati siano stati scaricati in ogni singolo caso. Chi ha avuto rapporti con DTU dal 2003 dovrebbe seguire le istruzioni dell'università, prestare attenzione a comunicazioni inattese, non approvare richieste di autenticazione non richieste e cambiare le password riutilizzate su altri servizi.</p>
<p class="av-source-reference">Fonti ufficiali: <a href="https://www.dtu.dk/english/NewsArchive/2026/10/Cyberattack-on-DTU_Notification-of-a-personal-data-breach" rel="noopener noreferrer">DTU – notifica della violazione dei dati</a>; <a href="https://dtu.dk/english/about/contact/it-information/timeline-of-the-cyberattack" rel="noopener noreferrer">DTU – timeline dell'attacco, aggiornata con i profili ospiti</a>; <a href="https://dtu.dk/english/about/contact/it-information" rel="noopener noreferrer">DTU – informazioni e raccomandazioni IT</a>.</p>"""
},
744: {
    "slug": "account-playstation-a-rischio-hacker-come-proteggersi",
    "title": "Account PlayStation: passkey, phishing e consigli per proteggersi",
    "seo": {"seo_title": "Account PlayStation: passkey e sicurezza",
            "seo_description": "Come proteggere l'account PlayStation: passkey, verifica in due passaggi, password uniche e attenzione ai messaggi fraudolenti.",
            "focus_keyphrase": "sicurezza account PlayStation"},
    "mode": "replace",
    "html": """<p>Un account PlayStation contiene acquisti digitali, dati personali, informazioni di pagamento e accesso ai servizi online. Per proteggerlo non serve inseguire ogni allarme generico: è più efficace attivare le funzioni di sicurezza disponibili e riconoscere i tentativi di furto delle credenziali. Questa guida riassume le indicazioni pubblicate da Sony e non segnala una nuova violazione dei sistemi PlayStation.</p>
<h2>Usa una passkey o la verifica in due passaggi</h2>
<p>PlayStation supporta le passkey, che consentono di accedere senza digitare la password tradizionale, usando il sistema di autenticazione del dispositivo. In alternativa è possibile attivare la verifica in due passaggi tramite SMS o app di autenticazione e conservare i codici di backup in un luogo sicuro. Non condividere mai i codici di verifica con persone che ti contattano dichiarando di essere del supporto tecnico.</p>
<h2>Riconosci i tentativi di phishing</h2>
<p>Diffida dei messaggi inattesi che segnalano un account sospeso, un acquisto da annullare, un premio da riscattare o un problema urgente da risolvere tramite un collegamento. Controlla il dominio del sito prima di inserire le credenziali e raggiungi la gestione account digitando direttamente l'indirizzo ufficiale o usando l'app PlayStation. Non fornire password, codici temporanei o dati di pagamento tramite chat o messaggi diretti.</p>
<h2>Proteggi anche e-mail e dispositivi</h2>
<p>L'indirizzo e-mail associato all'account è importante quanto la password PlayStation: usa una password unica e attiva anche lì l'autenticazione a più fattori. Evita di accedere da console pubbliche o dispositivi condivisi; se lo fai per necessità, esci dall'account al termine della sessione. Sulla console puoi impostare un codice di accesso e richiedere la password per gli acquisti sul PlayStation Store, così da ridurre il rischio di utilizzi non autorizzati.</p>
<h2>Se noti attività sospette</h2>
<p>Se ricevi notifiche di modifica dell'indirizzo e-mail o della password che non hai richiesto, oppure trovi acquisti che non riconosci, proteggi prima la casella e-mail, cambia il metodo di accesso e contatta il supporto PlayStation attraverso i canali ufficiali. Non affidarti a servizi o profili social che promettono di recuperare l'account in cambio di credenziali o pagamenti.</p>
<p class="av-source-reference">Fonti ufficiali: <a href="https://www.playstation.com/it-it/support/account/security-best-practice/" rel="noopener noreferrer">PlayStation – buone pratiche di sicurezza</a>; <a href="https://www.playstation.com/it-it/support/account/set-up-passkey/" rel="noopener noreferrer">PlayStation – configurare una passkey</a>; <a href="https://www.playstation.com/it-it/support/account/" rel="noopener noreferrer">PlayStation – account, sicurezza e verifica in due passaggi</a>; <a href="https://www.playstation.com/en-us/support/account/security-best-practice/" rel="noopener noreferrer">PlayStation – indicazioni sulle truffe tramite QR code e messaggi</a>.</p>"""
},
777: {
    "slug": "vulnerabilita-accesso-file-atlassian",
    "title": "CVE-2026-21589: vulnerabilità critica Atlassian e versioni corrette",
    "seo": {"seo_title": "CVE-2026-21589: prodotti Atlassian e patch",
            "seo_description": "La CVE-2026-21589 consente accesso arbitrario a file in prodotti Atlassian Data Center. Prodotti coinvolti, versioni corrette e mitigazioni.",
            "focus_keyphrase": "CVE-2026-21589 Atlassian"},
    "mode": "append",
    "html": """<h2>Aggiornamento del 16 novembre 2026: distinguere Cloud e Data Center</h2>
<p>L'avviso ufficiale Atlassian del 5 ottobre 2026 classifica la CVE-2026-21589 come vulnerabilità critica con punteggio CVSS 4.0 pari a 9,3. Riguarda le installazioni Data Center di Bitbucket, Confluence, Jira Service Management, Jira Software, Bamboo, Crowd, Crucible e Fisheye. Un attaccante non autenticato può accedere a file specifici nella directory radice dell'applicazione web, ma deve conoscere in anticipo il nome e il percorso esatti: la falla non consente di elencare automaticamente il contenuto delle directory.</p>
<p>È importante non confondere lo stato dei servizi Cloud con quello delle installazioni Data Center. Atlassian dichiara che i prodotti Cloud interessati sono stati corretti e che la propria indagine non ha rilevato prove di sfruttamento; questa comunicazione non equivale a una garanzia per le istanze Data Center gestite direttamente dai clienti. Per queste ultime resta necessario verificare la versione installata, applicare la patch corretta e controllare i log di accesso.</p>
<p>Le versioni correttive per i prodotti interessati sono riportate nell'avviso Atlassian e nel bollettino CERT-EU collegato qui sotto. Gli amministratori devono usare la versione corretta per il prodotto e il ramo specifico, aggiornando tutti i nodi del cluster. Se non è possibile applicare subito la patch, le mitigazioni temporanee indicate dal produttore prevedono la limitazione dell'accesso esterno e regole WAF o proxy; vanno implementate seguendo le istruzioni ufficiali e testate nell'ambiente interessato.</p>
<p class="av-source-reference">Fonti: <a href="https://confluence.atlassian.com/security/cve-2026-21589-arbitrary-file-access-vulnerability-impacts-multiple-products-1870495748.html" rel="noopener noreferrer">Atlassian – advisory ufficiale CVE-2026-21589</a>; <a href="https://www.cert.europa.eu/publications/security-advisories/2026-015/" rel="noopener noreferrer">CERT-EU – Security Advisory 2026-015</a>.</p>"""
},
810: {
    "slug": "vulnerabilita-jira-confluence-atlassian",
    "title": "CVE-2026-21589: patch e mitigazioni per Jira e Confluence Data Center",
    "seo": {"seo_title": "CVE-2026-21589: patch per Jira e Confluence",
            "seo_description": "Checklist per amministratori Jira e Confluence Data Center: verifica versione, applica patch, limita l'accesso e controlla i log.",
            "focus_keyphrase": "patch CVE-2026-21589 Jira Confluence"},
    "mode": "replace",
    "html": """<p>La vulnerabilità CVE-2026-21589 interessa le installazioni Atlassian Data Center e consente a un attaccante non autenticato di accedere a file specifici nell'area radice dell'applicazione web, se conosce già il percorso e il nome del file. La falla è classificata come critica. Questa pagina è una checklist operativa per gli amministratori di Jira e Confluence; per l'elenco completo dei prodotti interessati e di tutte le versioni correttive consulta anche la <a href="https://aivision.altervista.org/vulnerabilita-accesso-file-atlassian/">scheda AI Vision sulla vulnerabilità Atlassian</a>.</p>
<h2>1. Verifica se l'installazione è interessata</h2>
<p>Controlla se gestisci Jira Software Data Center, Jira Service Management Data Center o Confluence Data Center e rileva la versione esatta installata su ogni nodo. Non basarti soltanto sul nome del ramo: l'avviso del produttore elenca versioni correttive precise per ogni prodotto. Per Jira Software e Jira Service Management le versioni correttive indicate sono 9.12.40, 10.3.26 e 11.3.12; per Confluence Data Center sono 9.2.26 e 10.2.19. Verifica sempre la matrice aggiornata nell'advisory Atlassian prima di procedere.</p>
<h2>2. Applica l'aggiornamento correttivo</h2>
<p>Pianifica il passaggio alla versione corretta o a una versione successiva supportata, seguendo la procedura di aggiornamento Atlassian per il prodotto. In un cluster Data Center la correzione deve essere applicata a tutti i nodi, non soltanto al nodo principale. Prima dell'intervento esegui i backup previsti dalla procedura aziendale e verifica la compatibilità di app e componenti aggiuntivi.</p>
<h2>3. Se non puoi aggiornare subito</h2>
<p>Atlassian raccomanda, ove possibile, di rimuovere temporaneamente l'istanza dall'esposizione a Internet finché non sia possibile aggiornare o applicare una mitigazione. L'advisory descrive regole WAF o proxy e, per alcuni prodotti basati su Tomcat, configurazioni RewriteValve. Non copiare regole generiche da forum: usa i pattern e le istruzioni ufficiali, testali in ambiente controllato e applicali a tutti i nodi interessati.</p>
<h2>4. Controlla i log e documenta l'esito</h2>
<p>Esamina i log HTTP e applicativi per richieste anomale compatibili con tentativi di path traversal, conserva le evidenze e coinvolgi il team di sicurezza se emergono indicatori sospetti. L'installazione della patch riduce il rischio futuro ma non dimostra che l'istanza non sia stata già raggiunta. I prodotti Atlassian Cloud interessati risultano corretti automaticamente secondo il produttore; la checklist riguarda le installazioni Data Center gestite dal cliente.</p>
<p class="av-source-reference">Fonti operative: <a href="https://confluence.atlassian.com/security/cve-2026-21589-arbitrary-file-access-vulnerability-impacts-multiple-products-1870495748.html" rel="noopener noreferrer">Atlassian – CVE-2026-21589 e istruzioni di mitigazione</a>; <a href="https://www.cert.europa.eu/publications/security-advisories/2026-015/" rel="noopener noreferrer">CERT-EU – raccomandazioni per gli amministratori</a>.</p>"""
},
900: {
    "slug": "edward-dubrovsky-arrestato-shinyhunters",
    "title": "Edward Dubrovsky arrestato: le accuse e il caso ShinyHunters",
    "seo": {"seo_title": "Edward Dubrovsky: arresto e accuse ShinyHunters",
            "seo_description": "Le ricostruzioni di Reuters e KrebsOnSecurity sull'arresto in Pennsylvania e sulle accuse nel contesto dell'indagine ShinyHunters.",
            "focus_keyphrase": "Edward Dubrovsky ShinyHunters"},
    "mode": "replace",
    "html": """<p>Edward Dubrovsky, dirigente canadese nel settore della sicurezza informatica, è stato arrestato in Pennsylvania nell'ottobre 2026 nell'ambito di un'indagine federale collegata al gruppo ShinyHunters. Le informazioni disponibili derivano da resoconti giornalistici e da documenti giudiziari in parte non accessibili al pubblico: è quindi importante distinguere i fatti riportati dalle accuse e non presentare come accertata una responsabilità penale.</p>
<h2>Che cosa riportano le fonti</h2>
<p>Reuters, in un articolo dell'11 ottobre 2026, ha riferito che il dirigente è stato arrestato a Philadelphia e che i documenti giudiziari lo accusano di cospirazione finalizzata a minacciare la riservatezza delle informazioni con l'intento di estorcere denaro e di interferenza con il commercio tramite minacce. Reuters ha precisato che parte degli atti era secretata e che le autorità non avevano fornito pubblicamente tutti i dettagli sull'identità e sul ruolo attribuito all'indagato.</p>
<p>KrebsOnSecurity aveva riferito il 9 ottobre dell'arresto di un dirigente di una società canadese specializzata nella gestione delle negoziazioni legate alle estorsioni informatiche. La testata ha ricostruito alcuni passaggi attraverso registri giudiziari disponibili online, segnalando anche discrepanze nella trascrizione del cognome nei documenti. Questi elementi spiegano perché le prime ricostruzioni abbiano usato grafie differenti, ma non sostituiscono gli atti completi del procedimento.</p>
<h2>Il collegamento con ShinyHunters</h2>
<p>L'arresto è stato riportato nel contesto delle indagini dell'FBI su ShinyHunters e su presunte attività di estorsione informatica. Le fonti giornalistiche descrivono il gruppo come una realtà coinvolta in furti di dati e richieste di denaro per impedirne la pubblicazione. Tuttavia, il materiale pubblico citato nei resoconti non consente di ricostruire in modo completo il ruolo che Dubrovsky avrebbe avuto nelle singole operazioni attribuite al gruppo. È quindi scorretto trasformare il collegamento investigativo in una prova di partecipazione a ogni attacco.</p>
<h2>Accuse, non una condanna</h2>
<p>Le imputazioni riportate dai media sono accuse formulate nell'ambito di un procedimento penale e non equivalgono a una condanna. Poiché una parte della documentazione risulta non pubblica e non tutte le parti coinvolte hanno rilasciato dichiarazioni, eventuali sviluppi successivi devono essere verificati attraverso atti giudiziari o comunicazioni ufficiali. Questo articolo riporta il quadro documentato dalle fonti giornalistiche citate, senza attribuire colpe non accertate.</p>
<p class="av-source-reference">Fonti giornalistiche: <a href="https://www.reuters.com/legal/government/canadian-ransomware-negotiator-arrested-amid-fbi-hacker-crackdown-2026-10-11/" rel="noopener noreferrer">Reuters, 11 ottobre 2026 – arresto e accuse riportate</a>; <a href="https://krebsonsecurity.com/2026/10/fbi-arrests-founder-of-ransomware-negotiation-firm/" rel="noopener noreferrer">KrebsOnSecurity, 9 ottobre 2026 – ricostruzione dei registri giudiziari</a>.</p>"""
},
995: {
    "slug": "windows-11-24h2-fine-supporto-sicurezza",
    "title": "Windows 11 24H2: fine aggiornamenti per Home e Pro dal 13 ottobre 2026",
    "seo": {"seo_title": "Windows 11 24H2: fine aggiornamenti ottobre 2026",
            "seo_description": "Windows 11 24H2 Home, Pro e varianti hanno terminato gli aggiornamenti il 13 ottobre 2026. Scopri le versioni supportate e come aggiornare.",
            "focus_keyphrase": "fine supporto Windows 11 24H2"},
    "mode": "append",
    "html": """<h2>Aggiornamento del 16 novembre 2026: quali versioni installare</h2>
<p>Microsoft conferma che Windows 11 24H2 ha terminato gli aggiornamenti per le edizioni Home, Pro, Pro Education e Pro for Workstations il 13 ottobre 2026. L'aggiornamento mensile di ottobre è l'ultimo che include per queste edizioni le protezioni di sicurezza e gli aggiornamenti qualitativi. Le edizioni Enterprise ed Education di 24H2 restano invece supportate fino al 12 ottobre 2027.</p>
<p>Alla data di questo aggiornamento, Microsoft indica Windows 11 26H2 e 25H2 come versioni supportate per continuare a ricevere gli aggiornamenti mensili. La versione 26H2 è stata resa disponibile il 29 settembre 2026; Microsoft ha comunicato che la distribuzione ha raggiunto la piena disponibilità per i dispositivi idonei che eseguono 24H2 o 25H2. Per verificare la proposta sul proprio PC, apri Impostazioni, seleziona Windows Update e scegli Verifica disponibilità aggiornamenti. Se l'aggiornamento non viene ancora proposto, potrebbe esserci un blocco di compatibilità temporaneo: evita strumenti non ufficiali per forzare l'installazione e controlla gli avvisi di integrità della versione.</p>
<p>La fine del supporto non spegne il computer e non cancella i file: significa però che le edizioni non più supportate non ricevono nuove patch mensili. Antivirus e firewall non sostituiscono gli aggiornamenti del sistema operativo. Prima di procedere, verifica la versione con il comando winver e controlla che il dispositivo soddisfi i requisiti della versione successiva.</p>
<p class="av-source-reference">Fonti Microsoft: <a href="https://learn.microsoft.com/it-it/windows/release-health/windows11-release-information" rel="noopener noreferrer">Windows 11 – informazioni sulle versioni e date di fine aggiornamento</a>; <a href="https://learn.microsoft.com/it-it/windows/release-health/status-windows-11-24h2" rel="noopener noreferrer">stato e fine degli aggiornamenti di Windows 11 24H2</a>; <a href="https://learn.microsoft.com/it-it/windows/release-health/windows-message-center" rel="noopener noreferrer">Centro messaggi Windows – raccomandazione per 25H2 e 26H2</a>.</p>"""
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
    session.headers["User-Agent"] = "AIVision-Security-Article-Update/1.0"

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
            if post_id == 995:
                after_content = after_content.replace(
                    "Chi utilizza ancora il sistema operativo Windows 10 può inoltre contare sull'estensione gratuita del supporto garantita fino a ottobre 2027.",
                    "Windows 10 segue un calendario di supporto distinto: verifica le condizioni ufficiali applicabili al dispositivo prima di considerare disponibile un'estensione."
                )
            after_seo = dict(seo)
            after_seo.update(spec["seo"])
            changes.append({
                "id": post_id, "slug": spec["slug"], "modified": post.get("modified"),
                "before_title": (post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered"),
                "after_title": spec["title"], "before_content": raw, "after_content": after_content,
                "before_seo": seo, "after_seo": after_seo, "before_words": len(raw.split()),
                "after_words": len(after_content.split()), "mode": spec["mode"]
            })
        payload = {"site": BASE, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "changes": changes, "planned_updates": len(changes)}
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        BACKUP.write_text(json.dumps({
            "site": BASE, "created_at": payload["created_at"],
            "posts": [{"id": x["id"], "slug": x["slug"], "modified": x["modified"],
                       "title": x["before_title"], "content_raw": x["before_content"],
                       "aivision_seo": x["before_seo"]} for x in changes]
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Articoli di sicurezza pianificati:", len(changes))
        return 0

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("site") != BASE or not isinstance(plan.get("changes"), list):
        raise RuntimeError("Piano di aggiornamento non valido.")
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
            payload = {"title": row["after_title"], "content": row["after_content"],
                       "aivision_seo": row["after_seo"]}
            response = session.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",
                                    params={"context": "edit"}, json=payload,
                                    timeout=(8, 45), allow_redirects=False)
            seo_status = "saved"
            if not response.ok:
                # Se il bridge SEO rifiuta i metadati, salva comunque testo e titolo
                # in una seconda richiesta esplicita e registra l'avviso.
                fallback = session.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",
                                        params={"context": "edit"},
                                        json={"title": row["after_title"], "content": row["after_content"]},
                                        timeout=(8, 45), allow_redirects=False)
                fallback.raise_for_status()
                seo_status = "not_saved: " + response.text[:500]
            saved = read(row["id"])
            if ((saved.get("content") or {}).get("raw") != row["after_content"]
                    or ((saved.get("title") or {}).get("raw") or (saved.get("title") or {}).get("rendered")) != row["after_title"]):
                raise RuntimeError("Verifica titolo o contenuto fallita.")
            if seo_status == "saved":
                saved_seo = saved.get("aivision_seo") or {}
                if any(saved_seo.get(k) != v for k, v in row["after_seo"].items()):
                    seo_status = "warning: SEO non confermato dal bridge"
            results.append({"id": row["id"], "slug": row["slug"], "status": "updated_and_verified",
                            "seo_status": seo_status, "before_words": row["before_words"],
                            "after_words": row["after_words"], "title": row["after_title"]})
            print(f"Post {row['id']}: aggiornato e verificato ({seo_status}).")
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
