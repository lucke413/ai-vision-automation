"""
AI VISION - AI FILTER 2.6
Filtro editoriale intelligente con Gemini

INPUT:
    data/rss_output.json

OUTPUT:
    data/ai_candidates.json

Versione 2.6:
- filtro editoriale bilanciato
- classificazione categorie
- scoring AI
- valore per il lettore
- rilevanza italiana
- originalità
- valore commerciale
- urgenza
- selezione bilanciata per categoria
- gestione intelligente del rate limit Gemini 429
"""

import json
import os
import re
import time
import random
from collections import Counter

import requests


# ============================================================
# CONFIGURAZIONE
# ============================================================

VERSION = "2.6"

INPUT_FILE = "data/rss_output.json"
OUTPUT_FILE = "data/ai_candidates.json"

MODEL = "gemini-3.5-flash-lite"

MAX_ARTICLES = 80
MAX_FINAL_CANDIDATES = 20

# ------------------------------------------------------------
# RATE LIMIT GEMINI
# ------------------------------------------------------------

# Il limite rilevato sul progetto è 15 richieste/minuto.
# 6 secondi = circa 10 richieste/minuto.
REQUEST_DELAY = 6.0

# Numero massimo di tentativi per una singola richiesta
MAX_RETRIES = 4

# Piccolo margine aggiuntivo dopo il retryDelay di Gemini
RETRY_BUFFER = 2.0

# Timeout HTTP
REQUEST_TIMEOUT = 60


# ------------------------------------------------------------
# SOGLIE EDITORIALI
# ------------------------------------------------------------

MIN_AI_SCORE = 55
MIN_COLLECTOR_SCORE = 45
MIN_READER_VALUE = 45


# ------------------------------------------------------------
# LIMITI PER CATEGORIA
# ------------------------------------------------------------

CATEGORY_LIMITS = {
    "Smartphone & Mobile": 5,
    "PC & Hardware": 4,
    "Gaming": 4,
    "Software & App": 4,
    "AI": 4,
    "Sicurezza": 4,
    "Gadget & Consumer Tech": 4,
    "Streaming & Entertainment": 3,
    "Offerte & Prezzi": 3,
    "Tecnologia": 4,
}


# ============================================================
# CATEGORIE E TIPI
# ============================================================

VALID_CATEGORIES = [
    "Smartphone & Mobile",
    "PC & Hardware",
    "Gaming",
    "Software & App",
    "AI",
    "Sicurezza",
    "Gadget & Consumer Tech",
    "Streaming & Entertainment",
    "Offerte & Prezzi",
    "Tecnologia",
]


VALID_STORY_TYPES = [
    "OFFERTA",
    "RECENSIONE",
    "GUIDA",
    "SICUREZZA",
    "RUMOR",
    "SCIENZA",
    "ANALISI",
    "AZIENDALE",
    "NEWS",
]


# ============================================================
# PROMPT GEMINI
# ============================================================

SYSTEM_PROMPT = """
Sei il responsabile editoriale di AI Vision, un magazine italiano
generalista dedicato a tecnologia, prodotti, servizi digitali,
smartphone, PC, gaming, software, sicurezza, AI, gadget,
streaming e offerte.

OBIETTIVO:
Selezionare solo le notizie che possono diventare articoli utili,
interessanti e leggibili per un pubblico italiano generalista.

AI Vision NON deve essere un sito dedicato esclusivamente all'AI.

PRIORITÀ EDITORIALI:
- novità tecnologiche concrete
- nuovi prodotti
- smartphone
- PC e hardware
- gaming
- software e app
- sicurezza informatica
- gadget e consumer tech
- streaming
- offerte e prezzi
- guide utili
- cambiamenti che interessano realmente gli utenti
- AI quando è realmente interessante o utile

EVITARE:
- comunicati aziendali privi di interesse per il lettore
- notizie esclusivamente finanziarie
- risultati trimestrali
- contenuti autoreferenziali delle aziende
- notizie troppo tecniche
- articoli duplicati
- rumor molto deboli
- notizie senza conseguenze concrete per il lettore
- contenuti generici e banali
- contenuti che sembrano scritti solo per riempire il sito

VALUTA OGNI ARTICOLO INDIPENDENTEMENTE.

IMPORTANTE:
Non decidere in base alla fama della fonte.
Una fonte meno famosa può contenere una notizia molto interessante.

CORREGGI LA CATEGORIA SOLO QUANDO È EVIDENTEMENTE SBAGLIATA.
"""


def build_prompt(article):
    """
    Costruisce il prompt per Gemini.
    """

    title = article.get("title", "")
    description = article.get("description", "")
    source = article.get("source", "")
    category = article.get("category", "")
    story_type = article.get("story_type", "")

    return f"""
{SYSTEM_PROMPT}

Analizza il seguente articolo.

TITOLO:
{title}

DESCRIZIONE:
{description}

FONTE:
{source}

CATEGORIA ASSEGNATA DAL COLLECTOR:
{category}

TIPO ASSEGNATO DAL COLLECTOR:
{story_type}

Restituisci ESCLUSIVAMENTE un JSON valido con questa struttura:

{{
  "publishable": true,
  "ai_score": 0,
  "reason": "breve motivazione",
  "italian_relevance": 0,
  "originality": 0,
  "reader_value": 0,
  "urgency": 0,
  "commercial_value": 0,
  "format": "NEWS",
  "suggested_category": "Tecnologia",
  "suggested_story_type": "NEWS",
  "classification_issue": false
}}

REGOLE DEI PUNTEGGI:

ai_score:
0-100, qualità complessiva della notizia.

italian_relevance:
0-100, interesse per un pubblico italiano.

originality:
0-100, quanto la notizia aggiunge qualcosa rispetto a contenuti
tecnologici già molto comuni.

reader_value:
0-100, utilità/interesse concreto per il lettore.

urgency:
0-100, quanto è importante pubblicarla rapidamente.

commercial_value:
0-100, potenziale interesse verso prodotti, servizi, offerte,
confronti o acquisti.

format deve essere uno tra:
OFFERTA
RECENSIONE
GUIDA
SICUREZZA
RUMOR
SCIENZA
ANALISI
AZIENDALE
NEWS

suggested_category deve essere una tra:
Smartphone & Mobile
PC & Hardware
Gaming
Software & App
AI
Sicurezza
Gadget & Consumer Tech
Streaming & Entertainment
Offerte & Prezzi
Tecnologia

suggested_story_type deve essere uno tra:
OFFERTA
RECENSIONE
GUIDA
SICUREZZA
RUMOR
SCIENZA
ANALISI
AZIENDALE
NEWS

classification_issue deve essere true solo se la categoria o il tipo
assegnato dal collector è evidentemente errato.

publishable:
true solo se la notizia merita realmente un articolo su AI Vision.

Una notizia aziendale può essere pubblicabile solo se contiene
qualcosa di concretamente interessante per il lettore.

I rumor devono avere un motivo concreto per essere pubblicati.

Non premiare automaticamente l'AI: deve competere con tutte le altre
categorie del magazine.
"""


# ============================================================
# UTILITÀ
# ============================================================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clamp(value, minimum=0, maximum=100):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return minimum

    return max(minimum, min(maximum, value))


def normalize_text(value):
    if value is None:
        return ""

    return str(value).strip()


def extract_json(text):
    """
    Estrae JSON anche quando Gemini restituisce accidentalmente
    markdown o testo extra.
    """

    if not text:
        return None

    text = text.strip()

    # Caso ideale
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Rimuove eventuali blocchi markdown
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Cerca il primo oggetto JSON
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    return None


# ============================================================
# GEMINI API
# ============================================================

def get_api_key():
    """
    Recupera la chiave dalle GitHub Secrets.
    """

    api_key = os.environ.get("GEMINI_API_KEY", "")

    if not api_key:
        raise RuntimeError(
            "Variabile GEMINI_API_KEY non trovata."
        )

    # Rimuove accidentalmente spazi/newline copiati nel secret.
    api_key = api_key.strip()

    return api_key


def parse_retry_delay(error_response):
    """
    Cerca il tempo di attesa consigliato da Gemini.

    Priorità:
    1. details[].retryDelay
    2. testo 'Please retry in Xs'
    3. fallback None
    """

    # --------------------------------------------------------
    # Tentativo 1: struttura JSON Gemini
    # --------------------------------------------------------

    try:
        data = error_response.json()
    except Exception:
        data = {}

    details = (
        data
        .get("error", {})
        .get("details", [])
    )

    for detail in details:

        if not isinstance(detail, dict):
            continue

        # Formato tipico:
        # {
        #   "@type": "...RetryInfo",
        #   "retryDelay": "20s"
        # }

        retry_delay = detail.get("retryDelay")

        if retry_delay:
            match = re.search(
                r"([0-9]+(?:\.[0-9]+)?)",
                str(retry_delay)
            )

            if match:
                return float(match.group(1))

    # --------------------------------------------------------
    # Tentativo 2: cerca nel messaggio
    # --------------------------------------------------------

    try:
        message = (
            data
            .get("error", {})
            .get("message", "")
        )
    except Exception:
        message = ""

    if not message:
        try:
            message = error_response.text
        except Exception:
            message = ""

    match = re.search(
        r"retry in\s+([0-9]+(?:\.[0-9]+)?)s",
        message,
        flags=re.IGNORECASE
    )

    if match:
        return float(match.group(1))

    return None


def call_gemini(prompt, api_key):
    """
    Chiama Gemini con gestione intelligente del rate limit 429.

    In caso di 429:
    - legge retryDelay
    - aspetta il tempo indicato
    - aggiunge un piccolo margine
    - riprova
    """

    url = (
        f"https://generativelanguage.googleapis.com/"
        f"v1beta/models/{MODEL}:generateContent"
    )

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = requests.post(
                url,
                params={"key": api_key},
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )

            # ------------------------------------------------
            # SUCCESSO
            # ------------------------------------------------

            if response.status_code == 200:

                data = response.json()

                try:
                    text = (
                        data["candidates"][0]
                        ["content"]["parts"][0]["text"]
                    )
                except (KeyError, IndexError, TypeError):
                    print(
                        "    ERRORE: risposta Gemini senza contenuto valido"
                    )
                    return None

                return extract_json(text)

            # ------------------------------------------------
            # RATE LIMIT 429
            # ------------------------------------------------

            if response.status_code == 429:

                retry_delay = parse_retry_delay(response)

                if retry_delay is None:
                    # Fallback prudente se Gemini non comunica
                    # esplicitamente il tempo.
                    retry_delay = 30.0

                wait_time = retry_delay + RETRY_BUFFER

                print(
                    f"    429 Gemini - tentativo "
                    f"{attempt}/{MAX_RETRIES}"
                )

                print(
                    f"    Attendo {wait_time:.1f}s "
                    f"prima del nuovo tentativo..."
                )

                if attempt < MAX_RETRIES:
                    time.sleep(wait_time)
                    continue

                print(
                    "    ERRORE: numero massimo di tentativi 429 raggiunto."
                )

                return None

            # ------------------------------------------------
            # AUTENTICAZIONE
            # ------------------------------------------------

            if response.status_code in (400, 401, 403):

                print(
                    f"    ERRORE GEMINI HTTP {response.status_code}"
                )

                try:
                    error_data = response.json()

                    message = (
                        error_data
                        .get("error", {})
                        .get("message", "")
                    )

                    if message:
                        print(f"    {message}")

                except Exception:
                    print(response.text[:500])

                return None

            # ------------------------------------------------
            # ALTRI ERRORI HTTP
            # ------------------------------------------------

            print(
                f"    ERRORE GEMINI HTTP {response.status_code}"
            )

            try:
                print(response.text[:1000])
            except Exception:
                pass

            # Per errori temporanei 5xx, proviamo nuovamente.
            if 500 <= response.status_code < 600:

                if attempt < MAX_RETRIES:

                    # Backoff progressivo.
                    wait_time = (
                        (2 ** attempt) +
                        random.uniform(0.5, 1.5)
                    )

                    print(
                        f"    Nuovo tentativo tra "
                        f"{wait_time:.1f}s..."
                    )

                    time.sleep(wait_time)
                    continue

            return None

        except requests.exceptions.Timeout:

            print(
                f"    Timeout Gemini - tentativo "
                f"{attempt}/{MAX_RETRIES}"
            )

            if attempt < MAX_RETRIES:

                wait_time = (
                    3 +
                    random.uniform(0.5, 1.5)
                )

                print(
                    f"    Nuovo tentativo tra "
                    f"{wait_time:.1f}s..."
                )

                time.sleep(wait_time)
                continue

            return None

        except requests.exceptions.RequestException as exc:

            print(
                f"    Errore connessione Gemini: {exc}"
            )

            if attempt < MAX_RETRIES:

                wait_time = (
                    3 +
                    random.uniform(0.5, 1.5)
                )

                print(
                    f"    Nuovo tentativo tra "
                    f"{wait_time:.1f}s..."
                )

                time.sleep(wait_time)
                continue

            return None

        except Exception as exc:

            print(
                f"    Errore inatteso Gemini: {exc}"
            )

            return None

    return None


# ============================================================
# CALCOLO FINAL SCORE
# ============================================================

def calculate_final_score(article, ai):
    """
    Calcola il punteggio editoriale finale.

    Collector:
        35%

    AI:
        25%

    Reader value:
        15%

    Italian relevance:
        10%

    Originality:
        5%

    Commercial:
        5%

    Urgency:
        5%
    """

    collector_score = clamp(
        article.get("score", 0)
    )

    ai_score = clamp(
        ai.get("ai_score", 0)
    )

    reader_value = clamp(
        ai.get("reader_value", 0)
    )

    italian_relevance = clamp(
        ai.get("italian_relevance", 0)
    )

    originality = clamp(
        ai.get("originality", 0)
    )

    commercial_value = clamp(
        ai.get("commercial_value", 0)
    )

    urgency = clamp(
        ai.get("urgency", 0)
    )

    final_score = (
        collector_score * 0.35 +
        ai_score * 0.25 +
        reader_value * 0.15 +
        italian_relevance * 0.10 +
        originality * 0.05 +
        commercial_value * 0.05 +
        urgency * 0.05
    )

    category = normalize_text(
        ai.get(
            "suggested_category",
            article.get("category", "Tecnologia")
        )
    )

    story_type = normalize_text(
        ai.get(
            "suggested_story_type",
            article.get("story_type", "NEWS")
        )
    )

    # --------------------------------------------------------
    # Piccole penalizzazioni editoriali
    # --------------------------------------------------------

    # Offerte con basso valore commerciale:
    # probabilmente non sono vere offerte utili.
    if category == "Offerte & Prezzi" and commercial_value < 50:
        final_score -= 10

    # Rumor deboli.
    if story_type == "RUMOR" and ai_score < 75:
        final_score -= 8

    # AI aziendale / enterprise con poco valore per il lettore.
    if category == "AI" and commercial_value < 35 and reader_value < 60:
        final_score -= 5

    return round(
        max(0, min(100, final_score)),
        2
    )


# ============================================================
# CONTROLLO EDITORIALE
# ============================================================

def evaluate_article(article, ai):
    """
    Applica le regole editoriali 2.6.
    """

    reasons = []

    publishable = bool(
        ai.get("publishable", False)
    )

    ai_score = clamp(
        ai.get("ai_score", 0)
    )

    collector_score = clamp(
        article.get("score", 0)
    )

    reader_value = clamp(
        ai.get("reader_value", 0)
    )

    italian_relevance = clamp(
        ai.get("italian_relevance", 0)
    )

    commercial_value = clamp(
        ai.get("commercial_value", 0)
    )

    story_type = normalize_text(
        ai.get(
            "suggested_story_type",
            article.get("story_type", "NEWS")
        )
    )

    if not publishable:
        reasons.append("AI non approva")

    if ai_score < MIN_AI_SCORE:
        reasons.append(
            f"AI score troppo basso ({int(ai_score)})"
        )

    if collector_score < MIN_COLLECTOR_SCORE:
        reasons.append(
            f"Collector score troppo basso ({int(collector_score)})"
        )

    if reader_value < MIN_READER_VALUE:
        reasons.append(
            f"Reader value troppo basso ({int(reader_value)})"
        )

    # --------------------------------------------------------
    # RUMOR
    # --------------------------------------------------------

    if story_type == "RUMOR":

        if ai_score < 75:
            reasons.append("Rumor con score insufficiente")

        if italian_relevance < 50:
            reasons.append(
                "Rumor con bassa rilevanza italiana"
            )

    # --------------------------------------------------------
    # AZIENDALE
    # --------------------------------------------------------

    if story_type == "AZIENDALE":

        if ai_score < 75:
            reasons.append(
                "Contenuto aziendale con score insufficiente"
            )

        if reader_value < 60:
            reasons.append(
                "Contenuto aziendale con basso valore per il lettore"
            )

    # --------------------------------------------------------
    # OFFERTE
    # --------------------------------------------------------

    category = normalize_text(
        ai.get(
            "suggested_category",
            article.get("category", "Tecnologia")
        )
    )

    if category == "Offerte & Prezzi":

        if commercial_value < 50:
            reasons.append(
                "Offerta con valore commerciale insufficiente"
            )

    return (
        len(reasons) == 0,
        reasons
    )


# ============================================================
# NORMALIZZAZIONE RISPOSTA GEMINI
# ============================================================

def normalize_ai_response(ai, article):

    if not isinstance(ai, dict):
        return None

    result = {}

    result["publishable"] = bool(
        ai.get("publishable", False)
    )

    result["ai_score"] = int(
        clamp(ai.get("ai_score", 0))
    )

    result["reason"] = normalize_text(
        ai.get("reason", "")
    )

    result["italian_relevance"] = int(
        clamp(ai.get("italian_relevance", 0))
    )

    result["originality"] = int(
        clamp(ai.get("originality", 0))
    )

    result["reader_value"] = int(
        clamp(ai.get("reader_value", 0))
    )

    result["urgency"] = int(
        clamp(ai.get("urgency", 0))
    )

    result["commercial_value"] = int(
        clamp(ai.get("commercial_value", 0))
    )

    story_type = normalize_text(
        ai.get(
            "suggested_story_type",
            article.get("story_type", "NEWS")
        )
    )

    if story_type not in VALID_STORY_TYPES:
        story_type = article.get(
            "story_type",
            "NEWS"
        )

    result["suggested_story_type"] = story_type

    category = normalize_text(
        ai.get(
            "suggested_category",
            article.get("category", "Tecnologia")
        )
    )

    if category not in VALID_CATEGORIES:
        category = article.get(
            "category",
            "Tecnologia"
        )

    if category not in VALID_CATEGORIES:
        category = "Tecnologia"

    result["suggested_category"] = category

    result["format"] = normalize_text(
        ai.get("format", story_type)
    )

    result["classification_issue"] = bool(
        ai.get("classification_issue", False)
    )

    return result


# ============================================================
# SELEZIONE BILANCIATA
# ============================================================

def balanced_selection(candidates):
    """
    Seleziona massimo MAX_FINAL_CANDIDATES articoli evitando
    che una singola categoria domini il risultato.

    Prima fase:
    almeno un articolo per categoria quando disponibile.

    Seconda fase:
    riempimento per punteggio rispettando i limiti.

    Terza fase:
    fallback nel caso rimangano posti liberi.
    """

    if not candidates:
        return []

    candidates = sorted(
        candidates,
        key=lambda x: x.get("final_score", 0),
        reverse=True
    )

    selected = []
    category_counts = Counter()

    # --------------------------------------------------------
    # FASE 1
    # Un articolo per categoria
    # --------------------------------------------------------

    for article in candidates:

        category = article.get(
            "category",
            "Tecnologia"
        )

        limit = CATEGORY_LIMITS.get(
            category,
            4
        )

        if category_counts[category] >= limit:
            continue

        if category_counts[category] == 0:

            selected.append(article)
            category_counts[category] += 1

            if len(selected) >= MAX_FINAL_CANDIDATES:
                return selected

    # --------------------------------------------------------
    # FASE 2
    # Riempimento per punteggio
    # --------------------------------------------------------

    for article in candidates:

        if article in selected:
            continue

        category = article.get(
            "category",
            "Tecnologia"
        )

        limit = CATEGORY_LIMITS.get(
            category,
            4
        )

        if category_counts[category] >= limit:
            continue

        selected.append(article)
        category_counts[category] += 1

        if len(selected) >= MAX_FINAL_CANDIDATES:
            return selected

    # --------------------------------------------------------
    # FASE 3
    # Fallback
    # --------------------------------------------------------

    if len(selected) < MAX_FINAL_CANDIDATES:

        for article in candidates:

            if article in selected:
                continue

            selected.append(article)

            if len(selected) >= MAX_FINAL_CANDIDATES:
                break

    return selected


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("AI VISION - AI FILTER 2.6")
    print("=" * 70)
    print(f"VERSIONE FILTRO: {VERSION}")
    print(f"MODELLO: {MODEL}")
    print(f"INPUT: {INPUT_FILE}")
    print(f"OUTPUT: {OUTPUT_FILE}")
    print(f"ATTESA TRA RICHIESTE: {REQUEST_DELAY}s")
    print(f"MAX RETRY 429: {MAX_RETRIES}")
    print("=" * 70)

    # --------------------------------------------------------
    # API KEY
    # --------------------------------------------------------

    try:
        api_key = get_api_key()
    except Exception as exc:

        print(f"ERRORE: {exc}")
        return 1

    # --------------------------------------------------------
    # INPUT
    # --------------------------------------------------------

    if not os.path.exists(INPUT_FILE):

        print(
            f"ERRORE: file non trovato: {INPUT_FILE}"
        )

        return 1

    try:
        data = load_json(INPUT_FILE)
    except Exception as exc:

        print(
            f"ERRORE lettura JSON: {exc}"
        )

        return 1

    # --------------------------------------------------------
    # SUPPORTO AI DIVERSI FORMATI COLLECTOR
    # --------------------------------------------------------

    if isinstance(data, dict):

        articles = data.get(
            "items",
            data.get(
                "articles",
                data.get(
                    "stories",
                    []
                )
            )
        )

    elif isinstance(data, list):

        articles = data

    else:

        articles = []

    if not isinstance(articles, list):
        articles = []

    # Limite massimo
    articles = articles[:MAX_ARTICLES]

    print(
        f"Articoli ricevuti: {len(articles)}"
    )

    # --------------------------------------------------------
    # CONTATORI
    # --------------------------------------------------------

    analyzed = 0
    approved_ai = 0

    candidates = []

    exclusion_summary = Counter()

    all_analyzed = []

    # --------------------------------------------------------
    # ANALISI
    # --------------------------------------------------------

    for index, article in enumerate(articles, start=1):

        if not isinstance(article, dict):
            continue

        title = normalize_text(
            article.get("title", "")
        )

        if not title:
            exclusion_summary["Titolo mancante"] += 1
            continue

        print()
        print(
            f"[{index}/{len(articles)}] {title}"
        )

        # ----------------------------------------------------
        # Chiamata Gemini
        # ----------------------------------------------------

        prompt = build_prompt(article)

        ai_raw = call_gemini(
            prompt,
            api_key
        )

        # ----------------------------------------------------
        # Errore Gemini
        # ----------------------------------------------------

        if ai_raw is None:

            print(
                "    -> ERRORE Gemini dopo i retry"
            )

            exclusion_summary["Errore Gemini"] += 1

            all_analyzed.append({
                **article,
                "analysis_status": "gemini_error"
            })

            # Piccola pausa anche dopo un errore definitivo.
            time.sleep(REQUEST_DELAY)

            continue

        analyzed += 1

        # ----------------------------------------------------
        # Normalizzazione
        # ----------------------------------------------------

        ai = normalize_ai_response(
            ai_raw,
            article
        )

        if ai is None:

            print(
                "    -> Risposta Gemini non valida"
            )

            exclusion_summary[
                "Risposta Gemini non valida"
            ] += 1

            all_analyzed.append({
                **article,
                "analysis_status": "invalid_ai_response"
            })

            time.sleep(REQUEST_DELAY)

            continue

        # ----------------------------------------------------
        # Score
        # ----------------------------------------------------

        final_score = calculate_final_score(
            article,
            ai
        )

        approved, reasons = evaluate_article(
            article,
            ai
        )

        # ----------------------------------------------------
        # Categoria finale
        # ----------------------------------------------------

        original_category = article.get(
            "category",
            "Tecnologia"
        )

        final_category = ai.get(
            "suggested_category",
            original_category
        )

        if final_category not in VALID_CATEGORIES:

            final_category = original_category

        if final_category not in VALID_CATEGORIES:

            final_category = "Tecnologia"

        final_story_type = ai.get(
            "suggested_story_type",
            article.get("story_type", "NEWS")
        )

        if final_story_type not in VALID_STORY_TYPES:

            final_story_type = article.get(
                "story_type",
                "NEWS"
            )

        # ----------------------------------------------------
        # Log
        # ----------------------------------------------------

        print(
            f"    AI score: {ai['ai_score']}"
        )

        print(
            f"    Collector score: "
            f"{int(clamp(article.get('score', 0)))}"
        )

        print(
            f"    Reader value: "
            f"{ai['reader_value']}"
        )

        print(
            f"    Categoria: {final_category}"
        )

        print(
            f"    Tipo: {final_story_type}"
        )

        print(
            f"    Final score: {final_score}"
        )

        # ----------------------------------------------------
        # Salvataggio analisi completa
        # ----------------------------------------------------

        analyzed_article = {
            **article,
            "ai_analysis": ai,
            "category": final_category,
            "story_type": final_story_type,
            "final_score": final_score,
            "analysis_status": (
                "approved"
                if approved
                else "excluded"
            ),
        }

        if reasons:

            analyzed_article["exclusion_reasons"] = reasons

        all_analyzed.append(
            analyzed_article
        )

        # ----------------------------------------------------
        # APPROVAZIONE
        # ----------------------------------------------------

        if not approved:

            for reason in reasons:
                exclusion_summary[reason] += 1

            print(
                "    -> ESCLUSO"
            )

            time.sleep(REQUEST_DELAY)

            continue

        approved_ai += 1

        candidate = {
            **article,

            "category": final_category,
            "story_type": final_story_type,

            "ai_analysis": ai,

            "final_score": final_score,

            "editorial_reason": ai.get(
                "reason",
                ""
            ),
        }

        candidates.append(
            candidate
        )

        print(
            "    -> APPROVATO"
        )

        time.sleep(REQUEST_DELAY)

    # --------------------------------------------------------
    # SELEZIONE FINALE
    # --------------------------------------------------------

    selected = balanced_selection(
        candidates
    )

    # --------------------------------------------------------
    # Se qualche candidato approvato è rimasto fuori
    # --------------------------------------------------------

    selected_ids = {
        str(
            item.get(
                "url",
                item.get(
                    "title",
                    ""
                )
            )
        )
        for item in selected
    }

    for candidate in candidates:

        candidate_id = str(
            candidate.get(
                "url",
                candidate.get(
                    "title",
                    ""
                )
            )
        )

        if candidate_id not in selected_ids:

            exclusion_summary[
                "Escluso per bilanciamento categorie"
            ] += 1

    # --------------------------------------------------------
    # DISTRIBUZIONE CATEGORIE
    # --------------------------------------------------------

    category_distribution = Counter(
        item.get(
            "category",
            "Tecnologia"
        )
        for item in selected
    )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    output = {
        "filter_version": VERSION,

        "model": MODEL,

        "total_received": len(articles),

        "total_analyzed": analyzed,

        "total_passed_ai": approved_ai,

        "total_final_candidates": len(selected),

        "request_delay_seconds": REQUEST_DELAY,

        "max_retries": MAX_RETRIES,

        "category_distribution": dict(
            category_distribution
        ),

        "exclusion_summary": dict(
            exclusion_summary
        ),

        "items": selected,

        "all_analyzed": all_analyzed,
    }

    try:
        save_json(
            OUTPUT_FILE,
            output
        )
    except Exception as exc:

        print(
            f"ERRORE salvataggio output: {exc}"
        )

        return 1

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("RISULTATO AI FILTER")
    print("=" * 70)

    print(
        f"Articoli ricevuti: {len(articles)}"
    )

    print(
        f"Articoli analizzati: {analyzed}"
    )

    print(
        f"Approvati dall'AI: {approved_ai}"
    )

    print(
        f"Candidati finali: {len(selected)}"
    )

    print()
    print("DISTRIBUZIONE CATEGORIE")

    for category, count in sorted(
        category_distribution.items(),
        key=lambda x: (-x[1], x[0])
    ):

        print(
            f"- {category}: {count}"
        )

    print()

    if exclusion_summary:

        print("ESCLUSIONI")

        for reason, count in exclusion_summary.most_common():

            print(
                f"- {reason}: {count}"
            )

    print()
    print(
        f"Output salvato: {OUTPUT_FILE}"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
