#!/usr/bin/env python3
"""Inserisce guide pratiche verificate nel flusso AI Vision già esistente.

Non è un workflow aggiuntivo. Le schede sono materiali editoriali originali,
NON affermazioni di aver testato di persona software o interfacce.
Si controllano gli slug WordPress prima di proporre le schede: in caso
di API irraggiungibile non si pubblicano guide potenzialmente duplicate.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests
from requests.auth import HTTPBasicAuth

BASE_DIR = Path(__file__).resolve().parent.parent
CANDIDATES_PATH = BASE_DIR / "data" / "ai_candidates.json"
VERSION = "1.2"
MAX_INJECTED = 6
MAX_GUIDES = 4
MAX_TUTORIALS = 2

# Riferimenti ufficiali. Verificare periodicamente eventuali variazioni
# dell'interfaccia, delle disponibilità e delle condizioni dei servizi.
OFFICIAL = {
    "chatgpt_files": ("File in ChatGPT", "https://help.openai.com/en/articles/8555545"),
    "chatgpt_study": ("Modalità studio ChatGPT", "https://help.openai.com/en/articles/11780217-study-mode"),
    "chatgpt_images": ("Immagini in ChatGPT", "https://help.openai.com/en/articles/11084440-images-in-chatgpt"),
    "chatgpt_data": ("Analisi dati ChatGPT", "https://help.openai.com/en/articles/8437071"),
    "canva_images": ("Canva Magic Media", "https://www.canva.com/help/using-magic-media/"),
    "canva_video": ("Video generati con Canva AI", "https://www.canva.com/help/video-clip/"),
    "canva_design": ("Canva Magic Design", "https://www.canva.com/help/use-magic-design/"),
    "canva_effects": ("Animare immagini con Canva", "https://www.canva.com/help/ai-effects/"),
    "excel": ("Formule e Copilot in Excel", "https://support.microsoft.com/en-us/excel/copilot/data-insights-with-copilot-in-excel"),
}

# Gli articoli mostrano solo collegamenti per iniziare: le pagine di supporto
# (anche in inglese) rimangono nel brief interno per la verifica redazionale.
START_HERE = {
    "chatgpt": {
        "label": "Apri ChatGPT e prova il prompt",
        "url": "https://chatgpt.com/",
        "hint": "Apri ChatGPT, crea una conversazione e incolla il prompt di esempio. Adattalo alla tua situazione.",
    },
    "canva": {
        "label": "Apri Canva AI in italiano",
        "url": "https://www.canva.com/it_it/canva-ai/",
        "hint": "Esplora le funzioni AI disponibili nel tuo account, poi adatta la descrizione proposta qui sotto.",
    },
    "excel": {
        "label": "Scopri Excel in italiano",
        "url": "https://www.microsoft.com/it-it/microsoft-365/excel",
        "hint": "Inizia da un foglio di prova, leggi il prompt e controlla formule e risultati prima di usarli.",
    },
}


def advanced_example(topic: tuple) -> str:
    """Un prompt strutturato e subito personalizzabile per ogni argomento."""
    slug, audience, kind, title, objective, steps, example, caution, reference = topic
    base = [
        "Voglio ottenere un risultato pratico, non una spiegazione teorica.",
        f"ATTIVITÀ: {objective}",
        f"PARTI DA QUESTO ESEMPIO: {example}",
        "CONTESTO: [spiega a chi serve, dove verrà usato e quali dati reali hai].",
    ]
    if kind == "TUTORIAL":
        base.extend([
            "DESCRIZIONE DETTAGLIATA: specifica soggetto, ambiente, azione, inquadratura, stile, luce e atmosfera quando pertinenti.",
            "FORMATO: [orizzontale o verticale; durata indicativa se è un video].",
            "VINCOLI: non inserire loghi, scritte, persone reali o elementi non richiesti; se una funzione non è disponibile, dillo.",
            "RISULTATO: produci un risultato coerente con la descrizione e dimmi quali dettagli conviene migliorare.",
        ])
    else:
        base.extend([
            "PASSAGGI: proponi istruzioni concrete, una alla volta, adatte a chi parte da zero.",
            "FORMATO DEL RISULTATO: [scegli tabella, elenco, email, quiz, scaletta o altro formato utile].",
            "VINCOLI: usa soltanto i dati forniti, segnala i dati mancanti e non inventare informazioni.",
            "VERIFICA: mostra come controllare il risultato e quali errori cercare.",
        ])
    base.append("TONO: italiano chiaro, senza termini tecnici inutili.")
    return "\n".join(base)


def beginner_link(reference: str) -> dict:
    category = "chatgpt" if reference.startswith("chatgpt_") else ("canva" if reference.startswith("canva_") else "excel")
    return dict(START_HERE[category])


# slug, pubblico, formato, titolo, scopo, passi verificabili, prompt di esempio,
# verifica finale, documentazione ufficiale.
# I prompt sono esempi originali della redazione: non citazioni dei fornitori.
TOPICS = [
 ("email-lavoro-ia","Lavoro","GUIDA","Come preparare email professionali con l'AI senza perdere il proprio tono","Preparare una bozza di email partendo da scopo, destinatario e informazioni controllate.",
  ["Scrivere separatamente destinatario, obiettivo, tono richiesto e tre fatti che devono comparire.", "Chiedere una bozza con oggetto, apertura, messaggio e chiusura, poi richiedere una variante più breve.", "Rileggere nomi, scadenze e impegni prima di inviare, sostituendo ogni formulazione non desiderata."],
  "Scrivi una email cortese di 120 parole a un collega per proporre una riunione. Usa soltanto questi dati: [dati]. Evita promesse non indicate.",
  "Non inserire dati riservati o nomi reali negli esempi; nessun testo generato va inviato senza revisione.", "chatgpt_files"),
 ("riepilogo-riunione-ia","Lavoro","GUIDA","Trasformare appunti di riunione in attività e scadenze con l'AI","Distinguere decisioni confermate, incarichi e questioni ancora aperte.",
  ["Preparare appunti anonimi separando partecipanti, decisioni e punti da chiarire.", "Chiedere una tabella con attività, responsabile, scadenza e riferimento agli appunti; usare 'non indicato' quando manca un dato.", "Confrontare la tabella con gli appunti e ottenere un riepilogo finale da condividere solo dopo controllo."],
  "Da questi appunti anonimizzati ricava decisioni e attività. Non inventare scadenze o responsabili; segnala ogni dato mancante.",
  "L'AI non deve inventare accordi presi in riunione, né sostituire un verbale approvato.", "chatgpt_files"),
 ("presentazione-lavoro-ia","Lavoro","GUIDA","Preparare una presentazione di progetto usando l'AI","Organizzare obiettivo, pubblico, messaggi chiave e struttura delle slide.",
  ["Indicare durata, pubblico e risultato atteso prima di chiedere una scaletta.", "Chiedere una struttura con una sola idea per slide e note per chi presenta.", "Verificare dati e grafici, ridurre il testo e preparare domande frequenti sui punti deboli."],
  "Crea una scaletta di sei slide per illustrare questo progetto [descrizione]. Per ogni slide indica titolo, messaggio chiave e una proposta visiva.",
  "Non attribuire all'AI ricerche, dati di mercato o immagini che non siano state realmente verificate.", "canva_design"),
 ("excel-formule-ia","Lavoro","GUIDA","Chiedere aiuto all'AI per formule Excel e controllarne il risultato","Usare l'AI come assistente alla scrittura, non come prova della correttezza di una formula.",
  ["Preparare un foglio campione senza dati sensibili e descrivere la funzione di ogni colonna.", "Chiedere la formula e una spiegazione di ogni riferimento di cella; indicare lingua e versione di Excel.", "Provare la formula su almeno tre righe, incluse celle vuote o casi limite, e verificare il risultato manualmente."],
  "In Excel voglio calcolare la percentuale di variazione tra B2 e C2. Spiegami la formula, la divisione per zero e come verificarla.",
  "Le formule proposte possono essere scorrette o richiedere adattamenti a separatori e versioni diverse.", "excel"),
 ("report-dati-ia","Lavoro","GUIDA","Analizzare un piccolo foglio di dati con l'AI: domande utili","Partire da un file strutturato, chiedere tabelle leggibili e controllare i calcoli.",
  ["Usare un CSV di esempio privo di dati personali e spiegare il significato delle colonne.", "Chiedere medie, estremi e possibili errori di compilazione, non conclusioni commerciali non supportate.", "Confrontare almeno alcuni risultati con il file originario e riportare eventuali valori mancanti."],
  "Analizza il mio foglio di prova. Indica righe mancanti, valori anomali, una tabella riassuntiva e i passaggi di calcolo.",
  "Non condividere file aziendali riservati senza autorizzazione; una correlazione non dimostra causalità.", "chatgpt_data"),
 ("feedback-clienti-ia","Lavoro","GUIDA","Classificare commenti dei clienti con l'AI rispettando la privacy","Trasformare feedback anonimizzati in temi ricorrenti e priorità da verificare.",
  ["Rimuovere nomi, recapiti e dettagli identificativi dalle frasi prima di elaborarle.", "Chiedere di raggruppare solo i problemi effettivamente citati e di conservare esempi sintetici.", "Controllare manualmente i gruppi e contare il numero di frasi per categoria."],
  "Classifica questi dieci feedback anonimi in massimo cinque temi, usa esempi ricavati dal testo e segnala i commenti ambigui.",
  "Non attribuire emozioni, diagnosi o intenzioni a persone partendo da poche parole.", "chatgpt_files"),
 ("curriculum-ia","Lavoro","GUIDA","Migliorare la chiarezza del curriculum con l'AI senza inventare competenze","Riformulare esperienze autentiche in frasi verificabili e leggibili.",
  ["Elencare attività realmente svolte con parole semplici, senza recapiti o dati personali nel prompt di prova.", "Chiedere frasi brevi orientate alle responsabilità effettive, distinguendo risultati dimostrabili da ipotesi.", "Confrontare ogni frase con l'esperienza reale prima di copiare il testo nel CV."],
  "Rendi più chiara questa descrizione di mansioni [testo anonimo]. Non aggiungere strumenti, risultati o qualifiche che non ho indicato.",
  "Non far inventare date, titoli di studio o certificazioni: il contenuto del curriculum deve restare autentico.", "chatgpt_files"),
 ("pianificare-settimana-ia","Lavoro","GUIDA","Organizzare la settimana lavorativa con un piano creato dall'AI","Dividere incarichi in blocchi realistici senza affidare al modello decisioni automatiche.",
  ["Elencare attività, durate stimate e vincoli lasciando spazi per gli imprevisti.", "Chiedere una tabella con priorità, lavoro concentrato, pause e momenti di verifica.", "Spostare manualmente le attività incompatibili e aggiornare il piano quando cambiano gli impegni."],
  "Organizza queste attività [elenco] in cinque giorni: massimo due priorità al giorno, pause esplicite e margini per imprevisti.",
  "Le stime di durata restano ipotesi; non condividere calendari personali di altri senza consenso.", "chatgpt_files"),
 ("quiz-da-appunti","Scuola","GUIDA","Creare quiz di ripasso con l'AI partendo dai propri appunti","Favorire lo studio attivo usando domande collegate a un testo concreto.",
  ["Preparare un brano di studio o appunti propri, eliminando dati personali.", "Chiedere dieci domande di difficoltà crescente con risposte separate e riferimenti ai paragrafi.", "Rispondere senza guardare le soluzioni e correggere eventuali errori confrontando con il testo di partenza."],
  "Da questo testo [appunti] costruisci dieci domande di ripasso. Metti le soluzioni in fondo e non aggiungere informazioni esterne.",
  "Il quiz non deve sostituire libro, docente o verifica delle fonti originali.", "chatgpt_study"),
 ("mappe-concettuali-studio","Scuola","GUIDA","Preparare una mappa concettuale a partire da un capitolo con l'AI","Collegare idee principali e relazioni senza aggiungere nozioni non presenti.",
  ["Identificare il tema centrale e suddividere un capitolo in sezioni.", "Chiedere nodi sintetici e collegamenti espressi con verbi, limitandosi al materiale fornito.", "Disegnare la mappa e controllare le connessioni con il testo originale."],
  "Da questo capitolo [testo] proponi una mappa con un nodo centrale, sei concetti e i verbi che spiegano ogni collegamento.",
  "Verificare date, cause ed esempi: un diagramma ordinato può contenere connessioni sbagliate.", "chatgpt_study"),
 ("interrogazione-simulata","Scuola","GUIDA","Simulare un'interrogazione scolastica con l'AI","Esercitarsi a esporre un argomento e ricevere richieste di chiarimento.",
  ["Scegliere un argomento e inviare l'elenco dei punti del programma effettivamente studiati.", "Chiedere una domanda alla volta, senza mostrare subito la risposta.", "Dopo ogni risposta chiedere quali concetti risultano incompleti e confrontarli con gli appunti."],
  "Fai il professore di storia: interrogami su [argomento] con cinque domande, una alla volta; dopo ogni risposta dammi un suggerimento.",
  "Le valutazioni dell'AI sono indicative, non voti scolastici né correzioni ufficiali.", "chatgpt_study"),
 ("matematica-passaggi","Scuola","GUIDA","Usare l'AI per capire i passaggi di un esercizio di matematica","Privilegiare il ragionamento e la verifica finale rispetto alla sola soluzione.",
  ["Trascrivere il problema con dati, unità di misura e domanda finale.", "Chiedere un indizio alla volta e spiegare perché scegliere un'operazione.", "Rifare il procedimento senza AI e verificare il risultato per sostituzione o calcolo indipendente."],
  "Non risolvere subito questo esercizio [testo]. Fammi una domanda alla volta e aiutami a controllare i passaggi che propongo.",
  "I modelli possono commettere errori numerici: confrontare con il metodo usato a scuola.", "chatgpt_study"),
 ("studio-lingue-dialogo","Scuola","GUIDA","Allenare una lingua straniera con dialoghi guidati dall'AI","Imparare a formulare risposte e rivedere gli errori in contesto.",
  ["Definire lingua, livello indicativo e situazione quotidiana da simulare.", "Chiedere battute brevi una alla volta, con chiarimenti solo quando richiesti.", "Raccogliere le espressioni sbagliate, riscriverle e ripetere il dialogo senza suggerimenti."],
  "Facciamo un dialogo in inglese di livello base al ristorante. Scrivi una frase alla volta e correggi solo gli errori importanti.",
  "Pronuncia e idiomi vanno confrontati anche con materiali didattici affidabili.", "chatgpt_study"),
 ("riassunto-documento-studio","Scuola","GUIDA","Riassumere un documento di studio con l'AI e ritrovare i riferimenti","Rendere leggibile un testo lungo preservando concetti e dubbi.",
  ["Caricare un documento consentito o incollare un estratto identificando le sezioni.", "Chiedere un riassunto per argomenti con i punti non chiari esplicitamente segnalati.", "Confrontare ogni conclusione con il documento e correggere omissioni o citazioni inesatte."],
  "Riassumi questo documento [testo] in cinque temi. Per ogni tema indica quale sezione lo supporta e segnala ciò che non trovi.",
  "Evitare di presentare un riepilogo automatico come citazione letterale della fonte.", "chatgpt_files"),
 ("spiegare-con-parole-semplici","Scuola","GUIDA","Farsi spiegare un argomento difficile con esempi progressivi","Chiedere spiegazioni di complessità crescente senza perdere la precisione.",
  ["Scrivere quale parte non è chiara e che cosa si conosce già.", "Chiedere una spiegazione essenziale e un esempio verificabile, non metafore fuorvianti.", "Ripetere il concetto con parole proprie e confrontarlo con il manuale o gli appunti."],
  "Spiegami [concetto] con tre livelli di difficoltà. Dopo ciascuno fammi una domanda per verificare cosa ho capito.",
  "Le analogie possono semplificare troppo: verificare definizioni e termini del programma.", "chatgpt_study"),
 ("pianificare-viaggio-ia","Vita quotidiana","GUIDA","Pianificare un weekend con l'AI senza fidarsi di orari inventati","Ottenere una bozza di itinerario adattabile e verificare i dettagli variabili.",
  ["Indicare città, interessi, periodo, spostamenti e budget indicativo.", "Chiedere tappe ordinate per zona e tempi stimati chiaramente etichettati come approssimativi.", "Controllare su siti ufficiali apertura, biglietti, trasporti e accessibilità prima di prenotare."],
  "Proponi un itinerario di due giorni a [città] per una famiglia, con pause e alternative al coperto. Non inventare prezzi o orari.",
  "L'AI non garantisce disponibilità, orari, condizioni meteorologiche o costi aggiornati.", "chatgpt_files"),
 ("organizzare-spesa-ia","Vita quotidiana","GUIDA","Preparare una lista della spesa organizzata con l'AI","Convertire un piano di pasti non medico in ingredienti raggruppati.",
  ["Elencare le ricette scelte, il numero di persone e gli alimenti già disponibili.", "Chiedere una lista per categorie e quantità indicative senza inventare prodotti presenti in dispensa.", "Controllare porzioni, allergie dichiarate dagli interessati e disponibilità nel negozio."],
  "Da queste quattro ricette [lista] crea una spesa per tre persone raggruppata per reparto, sottraendo gli ingredienti già disponibili.",
  "Non usare l'AI per prescrizioni dietetiche o gestione di allergie senza indicazioni professionali.", "chatgpt_files"),
 ("confrontare-servizi-ia","Vita quotidiana","GUIDA","Confrontare servizi e abbonamenti con una tabella assistita dall'AI","Creare criteri trasparenti invece di affidarsi a classifiche inventate.",
  ["Scegliere criteri di confronto e raccogliere condizioni dai siti ufficiali dei servizi.", "Fornire dati e chiedere una tabella con prezzo, durata, rinnovi, limiti e punti mancanti.", "Evidenziare offerte scadute o voci da verificare prima della decisione."],
  "Confronta queste tre offerte [dati raccolti]. Non cercare di indovinare condizioni mancanti; metti 'da verificare' dove servono.",
  "Prezzi, disponibilità, clausole contrattuali e promozioni possono cambiare rapidamente.", "chatgpt_data"),
 ("scrivere-reclamo-ia","Vita quotidiana","GUIDA","Preparare una lettera di reclamo chiara con l'AI","Organizzare fatti cronologici e richiesta precisa con linguaggio civile.",
  ["Preparare date, numero ordine fittizio per la prova e descrizione documentata del problema.", "Chiedere una bozza formale che separi fatti, documenti allegati e richiesta.", "Verificare riferimenti contrattuali e sostituire i segnaposto prima dell'invio."],
  "Scrivi un reclamo gentile per questo problema [descrizione], con cronologia essenziale e richiesta chiara. Non citare leggi non fornite.",
  "Il modello non sostituisce assistenza legale; non deve creare norme, diritti o scadenze inventate.", "chatgpt_files"),
 ("immagini-prompt-chatgpt","Creatività","TUTORIAL","Creare immagini con ChatGPT: prompt, revisioni e limiti pratici","Imparare a descrivere soggetto, stile, composizione e formato dell'immagine.",
  ["Definire soggetto, ambiente, luce, inquadratura e ciò che non deve apparire.", "Generare una prima immagine e chiedere una sola modifica per volta, mantenendo gli elementi riusciti.", "Controllare dettagli, scritte e diritti d'uso prima di pubblicare l'immagine."],
  "Crea un'illustrazione editoriale di una scrivania futuristica con luce calda, formato orizzontale, senza loghi né testo.",
  "Le immagini possono contenere imprecisioni e non dimostrano che una scena sia reale.", "chatgpt_images"),
 ("ritoccare-immagine-chatgpt","Creatività","TUTORIAL","Modificare un'immagine con ChatGPT senza perdere la coerenza","Capire come descrivere modifiche locali evitando alterazioni indesiderate.",
  ["Usare una fotografia propria o per cui si hanno i permessi di modifica.", "Indicare precisamente che cosa cambiare e cosa mantenere invariato.", "Confrontare risultato e originale per rilevare dettagli involontariamente modificati."],
  "In questa mia immagine sostituisci lo sfondo con uno studio luminoso; mantieni invariati gli oggetti in primo piano.",
  "Le persone riconoscibili, i marchi e le opere altrui richiedono attenzione a consenso e diritti.", "chatgpt_images"),
 ("locandina-canva-ia","Creatività","TUTORIAL","Creare una locandina con Canva e immagini generate dall'AI","Combinare immagine, gerarchia visiva, testo e verifica dei diritti.",
  ["Definire titolo, informazioni indispensabili e dimensioni della locandina.", "Descrivere un'immagine nel generatore Canva Magic Media e scegliere una composizione leggibile.", "Aggiungere il testo nell'editor, rivedere ortografia e contrasto, esportare nel formato richiesto."],
  "Genera un'immagine di sfondo per una locandina di un evento scientifico scolastico: stile illustrato, spazio libero per il titolo.",
  "Disponibilità dei modelli e limiti del piano possono variare; verificare licenze e utilizzo commerciale.", "canva_images"),
 ("video-breve-canva-ai","Creatività","TUTORIAL","Realizzare un breve video generato con Canva AI passo per passo","Impostare una clip semplice con soggetto, azione e stile coerente.",
  ["Preparare una descrizione breve del soggetto, dell'azione e dell'inquadratura.", "Usare la funzione video quando disponibile nel proprio piano e valutare i risultati generati.", "Rifinire il clip nell'editor, aggiungendo testo accessibile e controllando suono e ritmo."],
  "Genera una breve clip con un taccuino su una scrivania; una mano apre il quaderno, luce naturale, camera fissa.",
  "Durata, risoluzione, lingua del prompt e crediti possono cambiare: consultare la guida ufficiale corrente.", "canva_video"),
 ("animare-foto-canva","Creatività","TUTORIAL","Da una foto a un video con gli effetti AI di Canva","Comprendere la trasformazione di una singola immagine in una clip.",
  ["Scegliere una foto di proprietà o autorizzata e verificare dimensioni e qualità.", "Esplorare gli effetti AI disponibili e selezionare quello adatto alla scena.", "Controllare deformazioni e continuità del risultato prima di scaricare o montare il video."],
  "Vorrei animare una foto di un paesaggio creando un movimento leggero delle nuvole, senza introdurre nuovi edifici o persone.",
  "Gli effetti possono cambiare e non tutti sono disponibili in ogni account o formato.", "canva_effects"),
 ("thumbnail-video-ia","Creatività","TUTORIAL","Preparare una copertina per video con immagini AI e testo leggibile","Creare una miniatura riconoscibile anche a dimensioni ridotte.",
  ["Scegliere un messaggio principale e una sola immagine che lo rappresenti.", "Generare una base visiva senza testo, poi aggiungere parole brevi nell'editor grafico.", "Controllare leggibilità e veridicità della copertina sullo schermo di uno smartphone."],
  "Crea un'illustrazione per la copertina di un video che spiega cos'è l'AI, fondo blu scuro, elemento centrale ben visibile, senza scritte.",
  "Evita immagini ingannevoli che facciano credere di mostrare fatti o prodotti inesistenti.", "canva_images"),
 ("storyboard-reel-ia","Creatività","TUTORIAL","Ideare lo storyboard di un Reel con l'aiuto dell'AI","Costruire una sequenza breve e comprensibile prima di realizzare le clip.",
  ["Definire pubblico, messaggio e durata complessiva indicativa.", "Chiedere una scaletta di inquadrature con azione, parlato e testo a schermo.", "Rivedere la sequenza, togliere promesse non verificabili e aggiungere didascalie accessibili."],
  "Scrivi uno storyboard di cinque scene per un Reel che spiega un trucco digitale utile. Per scena indica immagine, voce e testo breve.",
  "Lo storyboard è un progetto, non un video già creato; controllare diritti di suoni, clip e immagini usate.", "canva_design"),
 ("presentazione-canva-ai","Creatività","TUTORIAL","Realizzare una presentazione visiva con Canva Magic Design","Partire da un contenuto verificato per creare una struttura grafica coerente.",
  ["Preparare una scaletta di argomenti e dati già verificati.", "Esplorare proposte grafiche, poi modificare ordine e densità del testo.", "Esportare e rileggere ogni slide per grafici sbagliati, testo tagliato e problemi di contrasto."],
  "Prepara idee per sei slide su come studiare meglio, con titoli brevi, un esempio concreto e una domanda finale.",
  "Un layout professionale non rende automaticamente vere le informazioni inserite.", "canva_design"),
]

def editorial_brief(topic: tuple) -> str:
    slug, audience, kind, title, objective, steps, example, caution, reference = topic
    lines = [
        "SCHEDA EDITORIALE ORIGINALE AI VISION - non è una prova pratica del software.",
        f"Argomento: {title}. Settore: {audience}. Formato: {kind}.",
        f"Obiettivo verificabile della guida: {objective}",
        "Percorso didattico suggerito, da spiegare con esempi e senza inventare pulsanti o funzioni:",
    ]
    lines += [f"Passaggio {n}: {step}" for n, step in enumerate(steps, 1)]
    lines.extend([
        f"Esempio originale di richiesta che il lettore può personalizzare: {example}",
        f"Verifica finale e limiti: {caution}",
        "Metodo: spiegare cosa preparare, perché ogni passaggio è utile e cosa controllare dopo.",
        "Non spacciare il risultato dell'AI per una verifica indipendente, una ricerca online in tempo reale o un'esperienza diretta.",
        "Non inventare prezzi, licenze, versioni, disponibilità di pulsanti o interfacce: variano secondo piano, dispositivo e aggiornamenti.",
        "Invitare a usare dati dimostrativi e anonimi anziché documenti personali, password, contatti o altri dati riservati.",
        "Inserire un esempio personalizzabile, rendere esplicite le incertezze e offrire un metodo di controllo da parte del lettore.",
        "Se i materiali non dimostrano una funzione specifica, non attribuirla al programma.",
        "Il materiale di riferimento ufficiale serve per descrivere lo strumento in modo prudente, non è licenza per copiarne i contenuti.",
        f"Riferimento ufficiale del servizio: {OFFICIAL[reference][1]}",
    ])
    return "\n".join(lines)


# Example output to illustrate a real learning step, never a screenshot or
# a claim that the service produced the output. Each sector has concrete data.
def visual_demo(slug: str, audience: str, kind: str, steps: list[str]) -> dict:
    if "matematica" in slug:
        return {"heading": "Esempio svolto: 3x + 5 = 20",
                "lines": ["1. Sottrai 5: 3x = 15", "2. Dividi per 3: x = 5",
                          "3. Verifica: 3 × 5 + 5 = 20"]}
    if "spesa" in slug:
        return {"heading": "Esempio: lista della spesa",
                "lines": ["Ortofrutta: pomodori, mele", "Dispensa: pasta, legumi",
                          "Freschi: latte, yogurt"]}
    if "quiz" in slug or "interrogazione" in slug:
        return {"heading": "Esempio: quiz di ripasso",
                "lines": ["D: Qual è l'idea principale?", "R: Spiegala con parole tue",
                          "Controllo: confronta con il libro"]}
    if "excel" in slug or "dati" in slug:
        return {"heading": "Esempio: tabella di verifica",
                "lines": ["Voce A: 10 → 15", "Variazione: (15 − 10)/10 = 50%",
                          "Controllo: verifica i valori"]}
    if kind == "TUTORIAL":
        return {"heading": "Esempio di composizione visiva",
                "lines": ["Soggetto: scrivania creativa", "Luce: naturale e morbida",
                          "Formato: orizzontale, senza loghi"]}
    if audience == "Lavoro":
        return {"heading": "Esempio: risultato organizzato",
                "lines": ["Obiettivo: comunicare con chiarezza", "Bozza: struttura in 3 sezioni",
                          "Controllo: fatti, nomi e scadenze"]}
    if audience == "Scuola":
        return {"heading": "Esempio: apprendimento guidato",
                "lines": ["1. Leggi e comprendi il testo", "2. Rispondi senza suggerimenti",
                          "3. Confronta con la fonte"]}
    return {"heading": "Esempio: risultato pratico",
            "lines": ["Input: indica cosa ti serve", "Output: elenco ordinato per temi",
                      "Controllo: rivedi i dati reali"]}


def make_candidate(topic: tuple) -> dict:
    slug, audience, kind, title, objective, steps, example, caution, reference = topic
    label, url = OFFICIAL[reference]
    digest = hashlib.sha256(("aivision-guide:" + slug).encode("utf-8")).hexdigest()[:20]
    return {
        "article_id": "av-guide-" + digest,
        "cluster_id": "av-guide-" + digest,
        "topic_slug": slug,
        "title": title,
        "description": objective + " " + " ".join(steps) + " " + caution,
        "source_text": editorial_brief(topic),
        "source_text_status": "editorial_brief",
        "source_text_word_count": len(editorial_brief(topic).split()),
        "source": "AIVision - scheda editoriale originale",
        "url": beginner_link(reference)["url"],
        "image": "",
        "image_license": "not_applicable",
        "category": "AI",
        "story_type": "GUIDA",
        "editorial_kind": kind,
        "topic_audience": audience,
        "official_links": [beginner_link(reference)],
        "technical_reference": {"label": label, "url": url},
        "illustration_steps": [step.split(",")[0][:55] for step in steps],
        "example_prompt": example,
        "advanced_prompt": advanced_example(topic),
        "prompt_goal": objective,
        "result_check": caution,
        "visual_demo": visual_demo(slug, audience, kind, steps),
        "final_score": 82 if kind == "GUIDA" else 80,
        "ai_analysis": {"ai_score": 80},
        "affiliate_candidate": False,
    }

def wp_post_exists(session: requests.Session, base_url: str, slug: str) -> bool:
    root = base_url.rstrip("/")
    endpoint = root + ("/wp/v2/posts" if root.endswith("/wp-json") else "/wp-json/wp/v2/posts")
    for status in ("publish", "future"):
        response = session.get(
            endpoint,
            params={"slug": slug, "status": status, "per_page": 1},
            timeout=12,
        )
        response.raise_for_status()
        posts = response.json()
        if not isinstance(posts, list):
            raise ValueError("Risposta WordPress non valida")
        if any(post.get("slug") == slug for post in posts):
            return True
    return False

def inject(data: dict, date_key: str, is_published) -> dict:
    items = data.get("items")
    if data.get("status") not in {"ok", "ok_with_warnings", "empty"} or not isinstance(items, list):
        raise ValueError("Candidati AI non validi")
    existing = {str(x.get("cluster_id") or x.get("article_id") or "") for x in items}
    ordered = sorted(TOPICS, key=lambda t: hashlib.sha256((date_key + ":" + t[0]).encode("utf-8")).hexdigest())
    added = []
    groups = Counter()
    for topic in ordered:
        if len(added) >= MAX_INJECTED:
            break
        kind = topic[2]
        limit = MAX_GUIDES if kind == "GUIDA" else MAX_TUTORIALS
        if groups[kind] >= limit:
            continue
        candidate = make_candidate(topic)
        if candidate["cluster_id"] in existing:
            continue
        if is_published(candidate["topic_slug"]):
            continue
        if len(candidate["source_text"].split()) < 140:
            continue
        added.append(candidate)
        groups[kind] += 1
        existing.add(candidate["cluster_id"])
    result = dict(data)
    result["items"] = items + added
    result["total_final_candidates"] = len(result["items"])
    result["practical_guide_candidates"] = len(added)
    counts = Counter(str(x.get("category") or "Tecnologia") for x in result["items"])
    result["category_distribution"] = dict(counts)
    return result

def main() -> int:
    data = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))
    base_url = os.environ.get("WP_BASE_URL", "").strip().rstrip("/")
    username = os.environ.get("WP_USERNAME", "").strip()
    password = os.environ.get("WP_APP_PASSWORD", "").strip()
    # Senza una verifica autenticata, non scegliere guide potenzialmente già programmate.
    if not base_url.startswith("https://") or not username or not password:
        print("AVVISO guide: credenziali WordPress insufficienti, proseguo solo con le notizie.")
        return 0
    session = requests.Session()
    session.auth = HTTPBasicAuth(username, password)
    session.headers["User-Agent"] = "AI-Vision-Guide-Selector/1.0"
    tz = ZoneInfo("Europe/Rome")
    today = datetime.now(tz).strftime("%Y-%m-%d")
    try:
        def exists(slug: str) -> bool:
            return wp_post_exists(session, base_url, slug)
        result = inject(data, today, exists)
    except (requests.RequestException, ValueError) as exc:
        # Non abbassare le difese anti-duplicato quando WordPress è irraggiungibile.
        print(f"AVVISO guide: verifica WordPress non disponibile ({type(exc).__name__}); continuo con le notizie.")
        return 0
    temporary = CANDIDATES_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(CANDIDATES_PATH)
    print(f"AI VISION guide editoriali v{VERSION}: {result['practical_guide_candidates']} argomenti originali aggiunti al lotto; unico workflow.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
