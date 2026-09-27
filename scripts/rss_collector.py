#!/usr/bin/env python3

import os
import json
import time
import re
import requests
from collections import Counter


# ============================================================
# AI VISION - AI FILTER 2.6
# ============================================================

VERSION = "2.6"

INPUT_FILE = "data/rss_output.json"
OUTPUT_FILE = "data/ai_candidates.json"

MODEL = "gemini-3.5-flash-lite"

MAX_AI_ITEMS = 80
MAX_FINAL_CANDIDATES = 20

# ------------------------------------------------------------
# GEMINI RATE LIMIT
# ------------------------------------------------------------

REQUEST_DELAY = 6.0
MAX_RETRIES = 4
RETRY_BUFFER = 2.0

# ------------------------------------------------------------
# FILTER THRESHOLDS
# ------------------------------------------------------------

MIN_AI_SCORE = 55
MIN_COLLECTOR_SCORE = 45
MIN_READER_VALUE = 45

# ------------------------------------------------------------
# CATEGORY LIMITS
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
# GEMINI API
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{MODEL}:generateContent"
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
Sei il filtro editoriale automatico di AI Vision, un magazine italiano
generalista dedicato a tecnologia, prodotti, software, gaming, sicurezza,
AI, gadget, streaming, offerte e consigli pratici.

Il sito NON deve diventare un sito esclusivamente dedicato all'intelligenza
artificiale.

L'obiettivo è selezionare articoli che abbiano reale interesse per un lettore
italiano comune interessato alla tecnologia.

PRIORITÀ EDITORIALI:

- notizie tecnologiche realmente utili
- nuovi smartphone e dispositivi
- PC e hardware
- gaming
- software e applicazioni
- sicurezza informatica
- gadget e tecnologia consumer
- streaming e intrattenimento tecnologico
- offerte e prezzi
- guide pratiche
- confronti
- novità AI realmente utili

DA EVITARE:

- comunicati aziendali privi di utilità concreta
- risultati finanziari
- fatturato
- quotazioni
- investimenti
- funding
- acquisizioni puramente aziendali
- partnership senza impatto concreto sul consumatore
- notizie estremamente tecniche senza valore pratico
- contenuti ripetitivi
- notizie AI puramente promozionali
- rumor molto deboli
- contenuti che interessano esclusivamente addetti ai lavori

VALUTA OGNI ARTICOLO INDIPENDENTEMENTE.

Devi restituire esclusivamente JSON valido.
"""


# ============================================================
# UTILITY
# ============================================================

def clean_json_response(text):
    """
    Cerca di estrarre JSON anche se Gemini inserisce
    accidentalmente markdown o testo extra.
    """

    if not text:
        return None

    text = text.strip()

    # Rimuove eventuali blocchi markdown
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    # Cerca il primo oggetto JSON
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None


def parse_retry_delay(error_text):
    """
    Estrae il tempo di attesa suggerito da Gemini.
    """

    if not error_text:
        return None

    # Esempi:
    # retry in 20.512576461s
    # retry in 20s

    match = re.search(
        r"retry in\s+([0-9]+(?:\.[0-9]+)?)s",
        error_text,
        flags=re.I,
    )

    if match:
        try:
            return float(match.group(1))
        except Exception:
            pass

    # Cerca retryDelay nei messaggi JSON
    match = re.search(
        r'"retryDelay"\s*:\s*"([0-9]+(?:\.[0-9]+)?)s"',
        error_text,
        flags=re.I,
    )

    if match:
        try:
            return float(match.group(1))
        except Exception:
            pass

    return None


# ============================================================
# GEMINI REQUEST
# ============================================================

def call_gemini(prompt):
    if not API_KEY:
        raise RuntimeError(
            "Variabile GEMINI_API_KEY non trovata."
        )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY,
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            SYSTEM_PROMPT
                            + "\n\n"
                            + prompt
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    for attempt in range(MAX_RETRIES + 1):

        try:

            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=60,
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if response.status_code == 200:
                data = response.json()

                candidates = data.get(
                    "candidates",
                    [],
                )

                if not candidates:
                    raise RuntimeError(
                        "Gemini non ha restituito candidates."
                    )

                parts = (
                    candidates[0]
                    .get("content", {})
                    .get("parts", [])
                )

                if not parts:
                    raise RuntimeError(
                        "Gemini non ha restituito contenuto."
                    )

                text = parts[0].get(
                    "text",
                    "",
                )

                result = clean_json_response(text)

                if result is None:
                    raise RuntimeError(
                        "Risposta Gemini non interpretabile come JSON."
                    )

                return result

            # ------------------------------------------------
            # RATE LIMIT 429
            # ------------------------------------------------

            if response.status_code == 429:

                error_text = response.text

                retry_delay = parse_retry_delay(
                    error_text
                )

                if retry_delay is None:
                    retry_delay = (
                        10.0
                        * (attempt + 1)
                    )

                retry_delay += RETRY_BUFFER

                if attempt >= MAX_RETRIES:
                    raise RuntimeError(
                        "Gemini 429: limite richieste "
                        "raggiunto dopo tutti i tentativi."
                    )

                print(
                    f"  ⚠️ Gemini 429. "
                    f"Attendo {retry_delay:.1f}s "
                    f"prima del tentativo "
                    f"{attempt + 2}/{MAX_RETRIES + 1}..."
                )

                time.sleep(retry_delay)
                continue

            # ------------------------------------------------
            # SERVER ERRORS
            # ------------------------------------------------

            if response.status_code in (
                500,
                502,
                503,
                504,
            ):

                if attempt >= MAX_RETRIES:
                    raise RuntimeError(
                        f"Gemini errore server "
                        f"{response.status_code}: "
                        f"{response.text[:500]}"
                    )

                retry_delay = (
                    5.0
                    * (attempt + 1)
                )

                print(
                    f"  ⚠️ Gemini "
                    f"{response.status_code}. "
                    f"Riprovo tra "
                    f"{retry_delay:.1f}s..."
                )

                time.sleep(retry_delay)
                continue

            # ------------------------------------------------
            # OTHER ERRORS
            # ------------------------------------------------

            raise RuntimeError(
                f"Gemini HTTP {response.status_code}: "
                f"{response.text[:1000]}"
            )

        except requests.Timeout:

            if attempt >= MAX_RETRIES:
                raise RuntimeError(
                    "Timeout Gemini dopo tutti i tentativi."
                )

            retry_delay = (
                5.0
                * (attempt + 1)
            )

            print(
                f"  ⚠️ Timeout Gemini. "
                f"Riprovo tra "
                f"{retry_delay:.1f}s..."
            )

            time.sleep(retry_delay)

        except requests.ConnectionError:

            if attempt >= MAX_RETRIES:
                raise RuntimeError(
                    "Errore di connessione Gemini."
                )

            retry_delay = (
                5.0
                * (attempt + 1)
            )

            print(
                f"  ⚠️ Errore connessione. "
                f"Riprovo tra "
                f"{retry_delay:.1f}s..."
            )

            time.sleep(retry_delay)


# ============================================================
# GEMINI PROMPT
# ============================================================

def build_prompt(article):

    return f"""
Analizza il seguente articolo e restituisci un singolo oggetto JSON.

ARTICOLO:

Titolo:
{article.get("title", "")}

Descrizione:
{article.get("description", "")}

Fonte:
{article.get("source", "")}

Categoria Collector:
{article.get("category", "Tecnologia")}

Tipo Collector:
{article.get("story_type", "NEWS")}

Punteggio editoriale Collector:
{article.get("editorial_score", 0)}

Entità:
{", ".join(article.get("entities", []))}

Restituisci ESATTAMENTE questo schema:

{{
  "publishable": true,
  "score": 0,
  "reason": "",
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

REGOLE:

publishable:
true solo se il contenuto può diventare un articolo utile
e interessante per AI Vision.

score:
valutazione complessiva da 0 a 100.

italian_relevance:
quanto il contenuto è rilevante per un lettore italiano,
da 0 a 100.

originality:
quanto offre un argomento che merita un articolo autonomo,
da 0 a 100.

reader_value:
valore concreto per il lettore, da 0 a 100.

urgency:
attualità/importanza temporale, da 0 a 100.

commercial_value:
interesse commerciale legittimo per prodotti, servizi,
prezzi, acquisti o possibili contenuti utili al consumatore,
da 0 a 100.

format:
scegli uno tra:
NEWS
OFFERTA
RECENSIONE
GUIDA
SICUREZZA
RUMOR
SCIENZA
ANALISI
AZIENDALE

suggested_category:
scegli una sola categoria tra:

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

suggested_story_type:
scegli uno dei tipi sopra.

classification_issue:
true solo se la classificazione del Collector è chiaramente
sbagliata.

Non penalizzare automaticamente una notizia solo perché proviene
da una grande azienda. Penalizzala quando il contenuto è
prevalentemente aziendale e non offre un beneficio concreto
o un'informazione utile al lettore.

Le notizie AI devono essere valutate come tutte le altre:
non favorirle automaticamente e non penalizzarle automaticamente.
"""


# ============================================================
# ARTICLE EVALUATION
# ============================================================

def evaluate_article(article):

    prompt = build_prompt(article)

    result = call_gemini(prompt)

    if not isinstance(result, dict):
        result = {}

    return {
        "publishable": bool(
            result.get(
                "publishable",
                False,
            )
        ),

        "ai_score": int(
            result.get(
                "score",
                0,
            ) or 0
        ),

        "reason": str(
            result.get(
                "reason",
                "",
            )
        ),

        "italian_relevance": int(
            result.get(
                "italian_relevance",
                0,
            ) or 0
        ),

        "originality": int(
            result.get(
                "originality",
                0,
            ) or 0
        ),

        "reader_value": int(
            result.get(
                "reader_value",
                0,
            ) or 0
        ),

        "urgency": int(
            result.get(
                "urgency",
                0,
            ) or 0
        ),

        "commercial_value": int(
            result.get(
                "commercial_value",
                0,
            ) or 0
        ),

        "format": str(
            result.get(
                "format",
                article.get(
                    "story_type",
                    "NEWS",
                ),
            )
        ),

        "suggested_category": str(
            result.get(
                "suggested_category",
                article.get(
                    "category",
                    "Tecnologia",
                ),
            )
        ),

        "suggested_story_type": str(
            result.get(
                "suggested_story_type",
                article.get(
                    "story_type",
                    "NEWS",
                ),
            )
        ),

        "classification_issue": bool(
            result.get(
                "classification_issue",
                False,
            )
        ),
    }


# ============================================================
# FINAL SCORE
# ============================================================

def calculate_final_score(
    collector_score,
    ai_score,
    reader_value,
    italian_relevance,
    originality,
    commercial_value,
    urgency,
    story_type,
    category,
):

    score = (
        collector_score * 0.35
        + ai_score * 0.25
        + reader_value * 0.15
        + italian_relevance * 0.10
        + originality * 0.05
        + commercial_value * 0.05
        + urgency * 0.05
    )

    # ----------------------------------------
    # Small editorial adjustments
    # ----------------------------------------

    if (
        story_type == "OFFERTA"
        and commercial_value < 50
    ):
        score -= 8

    if (
        story_type == "RUMOR"
        and ai_score < 75
    ):
        score -= 8

    if (
        category == "AI"
        and commercial_value < 30
        and reader_value < 60
    ):
        score -= 5

    if story_type == "AZIENDALE":
        score -= 8

    return max(
        0,
        min(
            100,
            round(score),
        ),
    )


# ============================================================
# FILTER ARTICLE
# ============================================================

def filter_article(
    article,
    evaluation,
    exclusion_summary,
):

    # --------------------------------------------------------
    # IMPORTANT:
    # Collector 2.4 stores the score as "editorial_score"
    # NOT as "score".
    # --------------------------------------------------------

    collector_score = int(
        article.get(
            "editorial_score",
            0,
        ) or 0
    )

    ai_score = evaluation["ai_score"]
    reader_value = evaluation["reader_value"]
    italian_relevance = evaluation["italian_relevance"]
    originality = evaluation["originality"]
    commercial_value = evaluation["commercial_value"]
    urgency = evaluation["urgency"]

    story_type = evaluation[
        "suggested_story_type"
    ]

    category = evaluation[
        "suggested_category"
    ]

    # --------------------------------------------------------
    # Normalize invalid category/type
    # --------------------------------------------------------

    valid_categories = set(
        CATEGORY_LIMITS.keys()
    )

    valid_story_types = {
        "OFFERTA",
        "RECENSIONE",
        "GUIDA",
        "SICUREZZA",
        "RUMOR",
        "SCIENZA",
        "ANALISI",
        "AZIENDALE",
        "NEWS",
    }

    if category not in valid_categories:
        category = article.get(
            "category",
            "Tecnologia",
        )

    if category not in valid_categories:
        category = "Tecnologia"

    if story_type not in valid_story_types:
        story_type = article.get(
            "story_type",
            "NEWS",
        )

    if story_type not in valid_story_types:
        story_type = "NEWS"

    # --------------------------------------------------------
    # HARD RULES
    # --------------------------------------------------------

    if not evaluation["publishable"]:

        reason = "AI non approva"

        exclusion_summary[reason] += 1

        return None

    if collector_score < MIN_COLLECTOR_SCORE:

        reason = (
            f"Collector score troppo basso "
            f"({collector_score})"
        )

        exclusion_summary[reason] += 1

        return None

    if ai_score < MIN_AI_SCORE:

        reason = (
            f"AI score troppo basso "
            f"({ai_score})"
        )

        exclusion_summary[reason] += 1

        return None

    if reader_value < MIN_READER_VALUE:

        reason = (
            f"Reader value troppo basso "
            f"({reader_value})"
        )

        exclusion_summary[reason] += 1

        return None

    # --------------------------------------------------------
    # RUMOR
    # --------------------------------------------------------

    if story_type == "RUMOR":

        if ai_score < 75:

            exclusion_summary[
                "Rumor con score insufficiente"
            ] += 1

            return None

        if italian_relevance < 60:

            exclusion_summary[
                "Rumor con bassa rilevanza italiana"
            ] += 1

            return None

    # --------------------------------------------------------
    # AZIENDALE
    # --------------------------------------------------------

    if story_type == "AZIENDALE":

        if ai_score < 75:

            exclusion_summary[
                "Contenuto aziendale con score insufficiente"
            ] += 1

            return None

        if reader_value < 60:

            exclusion_summary[
                "Contenuto aziendale con basso valore per il lettore"
            ] += 1

            return None

    # --------------------------------------------------------
    # OFFERTE
    # --------------------------------------------------------

    if story_type == "OFFERTA":

        if commercial_value < 50:

            exclusion_summary[
                "Offerta con valore commerciale insufficiente"
            ] += 1

            return None

    # --------------------------------------------------------
    # FINAL SCORE
    # --------------------------------------------------------

    final_score = calculate_final_score(
        collector_score=collector_score,
        ai_score=ai_score,
        reader_value=reader_value,
        italian_relevance=italian_relevance,
        originality=originality,
        commercial_value=commercial_value,
        urgency=urgency,
        story_type=story_type,
        category=category,
    )

    # --------------------------------------------------------
    # Build final candidate
    # --------------------------------------------------------

    candidate = dict(article)

    candidate["category"] = category
    candidate["story_type"] = story_type

    candidate["collector_score"] = collector_score
    candidate["ai_score"] = ai_score
    candidate["reader_value"] = reader_value
    candidate["italian_relevance"] = italian_relevance
    candidate["originality"] = originality
    candidate["commercial_value"] = commercial_value
    candidate["urgency"] = urgency

    candidate["ai_reason"] = evaluation[
        "reason"
    ]

    candidate["classification_issue"] = evaluation[
        "classification_issue"
    ]

    candidate["final_score"] = final_score

    return candidate


# ============================================================
# BALANCED SELECTION
# ============================================================

def select_final_candidates(
    candidates,
    max_candidates=MAX_FINAL_CANDIDATES,
):

    if not candidates:
        return []

    ordered = sorted(
        candidates,
        key=lambda item: (
            item.get(
                "final_score",
                0,
            ),
            item.get(
                "ai_score",
                0,
            ),
            item.get(
                "reader_value",
                0,
            ),
        ),
        reverse=True,
    )

    selected = []

    category_counter = Counter()

    # --------------------------------------------------------
    # FIRST PASS
    # One article per category where possible.
    # This prevents AI Vision from becoming dominated by one
    # category.
    # --------------------------------------------------------

    for item in ordered:

        if len(selected) >= max_candidates:
            break

        category = item.get(
            "category",
            "Tecnologia",
        )

        limit = CATEGORY_LIMITS.get(
            category,
            4,
        )

        if category_counter[category] >= limit:
            continue

        if category_counter[category] == 0:

            selected.append(item)
            category_counter[category] += 1

    # --------------------------------------------------------
    # SECOND PASS
    # Fill remaining places according to score.
    # --------------------------------------------------------

    selected_ids = {
        item.get("id")
        for item in selected
    }

    for item in ordered:

        if len(selected) >= max_candidates:
            break

        item_id = item.get("id")

        if item_id in selected_ids:
            continue

        category = item.get(
            "category",
            "Tecnologia",
        )

        limit = CATEGORY_LIMITS.get(
            category,
            4,
        )

        if category_counter[category] >= limit:
            continue

        selected.append(item)
        selected_ids.add(item_id)
        category_counter[category] += 1

    # --------------------------------------------------------
    # FINAL FALLBACK
    # --------------------------------------------------------

    if len(selected) < max_candidates:

        for item in ordered:

            if len(selected) >= max_candidates:
                break

            item_id = item.get("id")

            if item_id in selected_ids:
                continue

            selected.append(item)
            selected_ids.add(item_id)

    return selected


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("AI VISION - AI FILTER 2.6")
    print("=" * 70)

    print(f"MODELLO: {MODEL}")
    print(f"INPUT: {INPUT_FILE}")
    print(f"OUTPUT: {OUTPUT_FILE}")
    print(
        f"ATTESA TRA RICHIESTE: "
        f"{REQUEST_DELAY}s"
    )
    print(
        f"MAX RETRY 429: "
        f"{MAX_RETRIES}"
    )

    # --------------------------------------------------------
    # LOAD INPUT
    # --------------------------------------------------------

    if not os.path.exists(INPUT_FILE):

        raise FileNotFoundError(
            f"File input non trovato: "
            f"{INPUT_FILE}"
        )

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    # --------------------------------------------------------
    # Extract articles
    # --------------------------------------------------------

    articles = data.get(
        "items",
        [],
    )

    if not articles:

        # Compatibility with collector structures
        articles = data.get(
            "articles",
            [],
        )

    if not articles:

        raise RuntimeError(
            "Nessun articolo trovato in "
            f"{INPUT_FILE}"
        )

    articles = articles[:MAX_AI_ITEMS]

    print(
        f"Articoli ricevuti: "
        f"{len(articles)}"
    )

    # --------------------------------------------------------
    # PROCESS
    # --------------------------------------------------------

    analyzed = []
    passed = []

    exclusion_summary = Counter()

    for index, article in enumerate(
        articles,
        start=1,
    ):

        title = article.get(
            "title",
            "",
        )

        print()
        print(
            f"[{index}/{len(articles)}] "
            f"{title[:100]}"
        )

        # --------------------------------------------
        # Gemini analysis
        # --------------------------------------------

        try:

            evaluation = evaluate_article(
                article
            )

        except Exception as exc:

            print(
                f"  ❌ Errore Gemini: {exc}"
            )

            exclusion_summary[
                "Errore Gemini"
            ] += 1

            continue

        # --------------------------------------------
        # IMPORTANT:
        # use editorial_score from RSS Collector
        # --------------------------------------------

        collector_score = int(
            article.get(
                "editorial_score",
                0,
            ) or 0
        )

        print(
            f"  Collector score: "
            f"{collector_score}"
        )

        print(
            f"  AI score: "
            f"{evaluation['ai_score']}"
        )

        print(
            f"  Reader value: "
            f"{evaluation['reader_value']}"
        )

        print(
            f"  AI approva: "
            f"{evaluation['publishable']}"
        )

        # --------------------------------------------
        # Evaluation record
        # --------------------------------------------

        analysis_record = dict(article)

        analysis_record["collector_score"] = (
            collector_score
        )

        analysis_record["ai_score"] = (
            evaluation["ai_score"]
        )

        analysis_record["reader_value"] = (
            evaluation["reader_value"]
        )

        analysis_record["italian_relevance"] = (
            evaluation["italian_relevance"]
        )

        analysis_record["originality"] = (
            evaluation["originality"]
        )

        analysis_record["commercial_value"] = (
            evaluation["commercial_value"]
        )

        analysis_record["urgency"] = (
            evaluation["urgency"]
        )

        analysis_record["ai_reason"] = (
            evaluation["reason"]
        )

        analysis_record[
            "suggested_category"
        ] = evaluation[
            "suggested_category"
        ]

        analysis_record[
            "suggested_story_type"
        ] = evaluation[
            "suggested_story_type"
        ]

        analysis_record[
            "classification_issue"
        ] = evaluation[
            "classification_issue"
        ]

        analyzed.append(
            analysis_record
        )

        # --------------------------------------------
        # Filter
        # --------------------------------------------

        candidate = filter_article(
            article,
            evaluation,
            exclusion_summary,
        )

        if candidate is not None:

            passed.append(candidate)

            print(
                f"  ✅ Candidato"
            )

            print(
                f"  Categoria: "
                f"{candidate['category']}"
            )

            print(
                f"  Tipo: "
                f"{candidate['story_type']}"
            )

            print(
                f"  Final score: "
                f"{candidate['final_score']}"
            )

        else:

            print(
                f"  ❌ Escluso"
            )

        # --------------------------------------------
        # Delay between Gemini requests
        # --------------------------------------------

        if index < len(articles):

            time.sleep(
                REQUEST_DELAY
            )

    # --------------------------------------------------------
    # FINAL SELECTION
    # --------------------------------------------------------

    final_candidates = select_final_candidates(
        passed,
        MAX_FINAL_CANDIDATES,
    )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    final_candidates = sorted(
        final_candidates,
        key=lambda item: item.get(
            "final_score",
            0,
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    output = {
        "filter_version": VERSION,

        "model": MODEL,

        "total_received": len(
            articles
        ),

        "total_analyzed": len(
            analyzed
        ),

        "total_passed_ai": len(
            passed
        ),

        "total_final_candidates": len(
            final_candidates
        ),

        "exclusion_summary": dict(
            exclusion_summary
        ),

        "items": final_candidates,

        "all_analyzed": analyzed,
    }

    os.makedirs(
        os.path.dirname(
            OUTPUT_FILE
        ),
        exist_ok=True,
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("RISULTATO AI FILTER 2.6")
    print("=" * 70)

    print(
        f"Articoli ricevuti: "
        f"{len(articles)}"
    )

    print(
        f"Articoli analizzati: "
        f"{len(analyzed)}"
    )

    print(
        f"Approvati dall'AI: "
        f"{len(passed)}"
    )

    print(
        f"Candidati finali: "
        f"{len(final_candidates)}"
    )

    print()
    print(
        "DISTRIBUZIONE CANDIDATI"
    )
    print("-" * 70)

    category_distribution = Counter(
        item.get(
            "category",
            "Tecnologia",
        )
        for item in final_candidates
    )

    for category, count in sorted(
        category_distribution.items(),
        key=lambda x: x[1],
        reverse=True,
    ):

        print(
            f"{category:<30} "
            f"{count}"
        )

    print()
    print(
        "TOP CANDIDATI"
    )
    print("-" * 70)

    for index, item in enumerate(
        final_candidates,
        start=1,
    ):

        print(
            f"{index:>2}. "
            f"[{item.get('final_score', 0):>3}] "
            f"[{item.get('category', '')}] "
            f"{item.get('title', '')}"
        )

    print()
    print(
        "ESCLUSIONI"
    )
    print("-" * 70)

    if exclusion_summary:

        for reason, count in sorted(
            exclusion_summary.items(),
            key=lambda x: x[1],
            reverse=True,
        ):

            print(
                f"{reason}: {count}"
            )

    else:

        print(
            "Nessuna esclusione."
        )

    print()
    print(
        f"Output salvato: "
        f"{OUTPUT_FILE}"
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
