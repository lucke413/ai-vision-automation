import json
import os
import time
from pathlib import Path
from collections import Counter

import requests


# ============================================================
# AI VISION - AI FILTER 2.6
# ============================================================

VERSION = "2.6"

INPUT_FILE = Path("data/rss_output.json")
OUTPUT_FILE = Path("data/ai_candidates.json")

MODEL = "gemini-3.5-flash-lite"

MAX_AI_ITEMS = 80
MAX_CANDIDATES = 20

REQUEST_DELAY = 1.0

# ============================================================
# SOGLIE - BASATE SULLA LOGICA 2.4
# ============================================================

MIN_AI_SCORE = 55
MIN_COLLECTOR_SCORE = 45
MIN_READER_VALUE = 45

# IMPORTANTE:
# il final_score NON viene più usato come filtro rigido.
# Serve principalmente per ordinare i candidati.
MIN_FINAL_SCORE = 0


# ============================================================
# LIMITI EDITORIALI
# ============================================================

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
# GEMINI
# ============================================================

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)


# ============================================================
# UTILITY
# ============================================================

def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def clamp(value, minimum=0, maximum=100):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return minimum

    return max(minimum, min(maximum, value))


def text(value):
    if value is None:
        return ""

    return str(value).strip()


def extract_json(raw_text):
    """
    Estrae JSON anche quando Gemini lo restituisce
    dentro un blocco markdown.
    """

    raw_text = raw_text.strip()

    if raw_text.startswith("```"):
        lines = raw_text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]

        raw_text = "\n".join(lines).strip()

    start = raw_text.find("{")
    end = raw_text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("Risposta Gemini priva di JSON valido")

    return json.loads(raw_text[start:end + 1])


# ============================================================
# GEMINI - VALUTAZIONE EDITORIALE
# ============================================================

def ask_gemini(item, api_key):

    title = text(item.get("title"))
    description = text(
        item.get("description")
        or item.get("summary")
        or item.get("content")
    )

    category = text(item.get("category"))
    story_type = text(item.get("story_type"))
    source = text(item.get("source"))

    prompt = f"""
Sei il responsabile editoriale di AI Vision, magazine tecnologico
italiano generalista rivolto a un pubblico consumer.

AI Vision tratta:

- Smartphone & Mobile
- PC & Hardware
- Gaming
- Software & App
- AI
- Sicurezza
- Gadget & Consumer Tech
- Streaming & Entertainment
- Offerte & Prezzi
- Tecnologia

L'intelligenza artificiale è una categoria importante, ma NON deve
dominare il magazine.

Devi valutare questa notizia esclusivamente dal punto di vista
editoriale.

DATI DEL COLLECTOR

Categoria:
{category}

Tipo:
{story_type}

Fonte:
{source}

Titolo:
{title}

Descrizione:
{description}

VALUTA:

1. Se può diventare un articolo interessante per AI Vision.
2. Quanto è utile per il lettore italiano.
3. Quanto è originale.
4. Quanto è attuale/importante.
5. Quanto può avere valore commerciale.
6. Se può essere trasformata in un buon articolo italiano.
7. Se è una vera offerta, vera recensione, vera guida o vera notizia.

REGOLE IMPORTANTI:

- Non inventare informazioni.
- Non considerare automaticamente un contenuto aziendale come interessante.
- Non considerare automaticamente ogni contenuto AI come prioritario.
- Non considerare ogni problema Windows/Android/iOS come sicurezza.
- Una vulnerabilità, un attacco, un malware o un exploit sono invece Sicurezza.
- Una recensione deve essere realmente una recensione.
- Un'offerta deve contenere un reale vantaggio economico.
- Un rumor deve essere trattato con maggiore prudenza.
- Le notizie puramente promozionali devono avere un punteggio basso.
- Considera il valore concreto per un lettore italiano.

IMPORTANTE SULLA CLASSIFICAZIONE:

Il Collector ha già assegnato categoria e tipo.
Non modificarli salvo errore evidente.

Se ritieni che ci sia un errore evidente, indicarlo nei campi
classification_issue, suggested_category e suggested_story_type.

RESTITUISCI ESCLUSIVAMENTE JSON VALIDO:

{{
  "publishable": true,
  "score": 0,
  "reason": "",
  "italian_relevance": 0,
  "originality_potential": 0,
  "reader_value": 0,
  "urgency": 0,
  "commercial_value": 0,
  "format": "",
  "classification_issue": false,
  "suggested_category": "",
  "suggested_story_type": ""
}}

Tutti i punteggi sono da 0 a 100.

"format" deve essere uno tra:

NEWS
GUIDA
RECENSIONE
SICUREZZA
OFFERTA
ANALISI
RUMOR
"""


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

    response = requests.post(
        GEMINI_URL,
        params={"key": api_key},
        json=payload,
        timeout=90
    )

    response.raise_for_status()

    data = response.json()

    candidates = data.get("candidates", [])

    if not candidates:
        raise RuntimeError(
            "Gemini non ha restituito candidates"
        )

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )

    if not parts:
        raise RuntimeError(
            "Gemini non ha restituito contenuto"
        )

    response_text = parts[0].get("text", "")

    return extract_json(response_text)


# ============================================================
# CORREZIONE CLASSIFICAZIONE
# ============================================================

def correct_classification(item, ai):

    category = text(
        item.get("category")
    ) or "Tecnologia"

    story_type = text(
        item.get("story_type")
    ) or "NEWS"

    if not ai.get("classification_issue"):
        return category, story_type

    suggested_category = text(
        ai.get("suggested_category")
    )

    suggested_story_type = text(
        ai.get("suggested_story_type")
    )

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
        "NEWS"
    }

    if suggested_category in valid_categories:
        category = suggested_category

    if suggested_story_type in valid_story_types:
        story_type = suggested_story_type

    return category, story_type


# ============================================================
# FINAL SCORE
# ============================================================

def calculate_final_score(item, ai):

    collector_score = clamp(
        item.get("score", 0)
    )

    ai_score = clamp(
        ai.get("score", 0)
    )

    reader_value = clamp(
        ai.get("reader_value", 0)
    )

    italian_relevance = clamp(
        ai.get("italian_relevance", 0)
    )

    originality = clamp(
        ai.get("originality_potential", 0)
    )

    commercial_value = clamp(
        ai.get("commercial_value", 0)
    )

    urgency = clamp(
        ai.get("urgency", 0)
    )

    # Formula base del 2.4
    final_score = (
        collector_score * 0.35
        + ai_score * 0.25
        + reader_value * 0.15
        + italian_relevance * 0.10
        + originality * 0.05
        + commercial_value * 0.05
        + urgency * 0.05
    )

    # --------------------------------------------------------
    # Correzioni editoriali leggere
    # --------------------------------------------------------

    story_type = item.get("story_type")
    category = item.get("category")

    # Le offerte non devono vincere automaticamente
    # grazie al solo valore commerciale.
    if story_type == "OFFERTA":
        if commercial_value < 50:
            final_score -= 5

    # I rumor richiedono maggiore qualità.
    if story_type == "RUMOR":
        if ai_score < 75:
            final_score -= 5

    # I contenuti aziendali vengono leggermente penalizzati.
    if story_type == "AZIENDALE":
        if ai_score < 75:
            final_score -= 5

    # AI non deve dominare semplicemente perché contiene la parola AI.
    if category == "AI":
        final_score -= 1

    return round(
        max(0, min(100, final_score)),
        2
    )


# ============================================================
# HARD RULES
# ============================================================

def evaluate_candidate(item, ai):

    reasons = []

    publishable = bool(
        ai.get("publishable", False)
    )

    ai_score = clamp(
        ai.get("score", 0)
    )

    collector_score = clamp(
        item.get("score", 0)
    )

    reader_value = clamp(
        ai.get("reader_value", 0)
    )

    story_type = item.get(
        "story_type",
        "NEWS"
    )

    commercial_value = clamp(
        ai.get("commercial_value", 0)
    )

    # --------------------------------------------------------
    # 1. Gemini deve approvare
    # --------------------------------------------------------

    if not publishable:
        reasons.append(
            "Gemini ha indicato publishable=false"
        )

    # --------------------------------------------------------
    # 2. AI score
    # --------------------------------------------------------

    if ai_score < MIN_AI_SCORE:
        reasons.append(
            f"AI score {ai_score:.0f} < {MIN_AI_SCORE}"
        )

    # --------------------------------------------------------
    # 3. Collector score
    # --------------------------------------------------------

    if collector_score < MIN_COLLECTOR_SCORE:
        reasons.append(
            f"Collector score {collector_score:.0f} "
            f"< {MIN_COLLECTOR_SCORE}"
        )

    # --------------------------------------------------------
    # 4. Valore per il lettore
    # --------------------------------------------------------

    if reader_value < MIN_READER_VALUE:
        reasons.append(
            f"Reader value {reader_value:.0f} "
            f"< {MIN_READER_VALUE}"
        )

    # --------------------------------------------------------
    # 5. Rumor
    # --------------------------------------------------------

    if story_type == "RUMOR":

        if ai_score < 75:
            reasons.append(
                "Rumor con AI score inferiore a 75"
            )

    # --------------------------------------------------------
    # 6. Aziendale
    # --------------------------------------------------------

    if story_type == "AZIENDALE":

        if ai_score < 75:
            reasons.append(
                "Contenuto aziendale con AI score inferiore a 75"
            )

    # --------------------------------------------------------
    # 7. Offerte
    # --------------------------------------------------------

    if story_type == "OFFERTA":

        if commercial_value < 50:
            reasons.append(
                "Offerta con valore commerciale inferiore a 50"
            )

    accepted = len(reasons) == 0

    return accepted, reasons


# ============================================================
# SELEZIONE BILANCIATA
# ============================================================

def select_balanced_candidates(candidates):

    if not candidates:
        return []

    # Prima ordiniamo tutto per final_score.
    ordered = sorted(
        candidates,
        key=lambda x: x.get(
            "final_score",
            0
        ),
        reverse=True
    )

    selected = []
    category_counts = Counter()

    # --------------------------------------------------------
    # PASSAGGIO 1
    #
    # Cerchiamo di avere almeno un rappresentante delle
    # categorie disponibili.
    # --------------------------------------------------------

    for item in ordered:

        if len(selected) >= MAX_CANDIDATES:
            break

        category = item.get(
            "category",
            "Tecnologia"
        )

        if category in category_counts:
            continue

        selected.append(item)
        category_counts[category] += 1

    # --------------------------------------------------------
    # PASSAGGIO 2
    #
    # Completiamo i 20 usando i punteggi migliori.
    # --------------------------------------------------------

    for item in ordered:

        if len(selected) >= MAX_CANDIDATES:
            break

        if item in selected:
            continue

        category = item.get(
            "category",
            "Tecnologia"
        )

        limit = CATEGORY_LIMITS.get(
            category,
            4
        )

        if category_counts[category] >= limit:
            continue

        selected.append(item)
        category_counts[category] += 1

    # --------------------------------------------------------
    # PASSAGGIO 3
    #
    # Se non arriviamo a 20 perché i limiti sono troppo stretti,
    # allarghiamo leggermente senza buttare via candidati validi.
    # --------------------------------------------------------

    if len(selected) < MAX_CANDIDATES:

        for item in ordered:

            if len(selected) >= MAX_CANDIDATES:
                break

            if item in selected:
                continue

            selected.append(item)

    # --------------------------------------------------------
    # Ordinamento finale
    # --------------------------------------------------------

    selected.sort(
        key=lambda x: x.get(
            "final_score",
            0
        ),
        reverse=True
    )

    return selected


# ============================================================
# MAIN
# ============================================================

def main():

    print("======================================")
    print("       AI VISION - AI FILTER 2.6")
    print("======================================")

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY non configurata"
        )

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"File non trovato: {INPUT_FILE}"
        )

    data = load_json(
        INPUT_FILE
    )

    items = data.get(
        "items",
        []
    )

    if not items:
        raise RuntimeError(
            "Nessun articolo trovato in rss_output.json"
        )

    # Massimo 80 articoli
    items = items[:MAX_AI_ITEMS]

    print(
        f"Articoli ricevuti: {len(items)}"
    )

    print(
        f"Modello: {MODEL}"
    )

    print("")

    analyzed = []
    passed_ai = []

    exclusion_counter = Counter()

    # ========================================================
    # GEMINI
    # ========================================================

    for index, item in enumerate(
        items,
        1
    ):

        print(
            f"[{index}/{len(items)}] "
            f"{item.get('title', '')}"
        )

        item_copy = dict(item)

        try:

            ai = ask_gemini(
                item,
                api_key
            )

        except Exception as exc:

            print(
                f"   ERRORE Gemini: {exc}"
            )

            item_copy["ai"] = {
                "publishable": False,
                "score": 0,
                "reason": (
                    f"Errore Gemini: {exc}"
                )
            }

            item_copy["final_score"] = 0

            item_copy["exclusion_reasons"] = [
                f"Errore Gemini: {exc}"
            ]

            analyzed.append(
                item_copy
            )

            exclusion_counter[
                "Errore Gemini"
            ] += 1

            time.sleep(
                REQUEST_DELAY
            )

            continue

        # ----------------------------------------------------
        # Classificazione
        # ----------------------------------------------------

        (
            corrected_category,
            corrected_story_type
        ) = correct_classification(
            item_copy,
            ai
        )

        item_copy["category"] = (
            corrected_category
        )

        item_copy["story_type"] = (
            corrected_story_type
        )

        item_copy["ai"] = ai

        # ----------------------------------------------------
        # Final score
        # ----------------------------------------------------

        final_score = calculate_final_score(
            item_copy,
            ai
        )

        item_copy["final_score"] = (
            final_score
        )

        # ----------------------------------------------------
        # Hard rules
        # ----------------------------------------------------

        accepted, reasons = evaluate_candidate(
            item_copy,
            ai
        )

        item_copy["exclusion_reasons"] = (
            reasons
        )

        if accepted:

            item_copy["ai"]["publishable"] = True

            passed_ai.append(
                item_copy
            )

        else:

            item_copy["ai"]["publishable"] = False

            for reason in reasons:

                if reason.startswith(
                    "Gemini ha indicato"
                ):
                    exclusion_counter[
                        "Gemini publishable=false"
                    ] += 1

                elif reason.startswith(
                    "AI score"
                ):
                    exclusion_counter[
                        "AI score insufficiente"
                    ] += 1

                elif reason.startswith(
                    "Collector score"
                ):
                    exclusion_counter[
                        "Collector score insufficiente"
                    ] += 1

                elif reason.startswith(
                    "Reader value"
                ):
                    exclusion_counter[
                        "Reader value insufficiente"
                    ] += 1

                elif reason.startswith(
                    "Rumor"
                ):
                    exclusion_counter[
                        "Rumor"
                    ] += 1

                elif reason.startswith(
                    "Contenuto aziendale"
                ):
                    exclusion_counter[
                        "Contenuto aziendale"
                    ] += 1

                elif reason.startswith(
                    "Offerta"
                ):
                    exclusion_counter[
                        "Offerta"
                    ] += 1

                else:
                    exclusion_counter[
                        reason
                    ] += 1

        analyzed.append(
            item_copy
        )

        time.sleep(
            REQUEST_DELAY
        )

    # ========================================================
    # SELEZIONE FINALE
    # ========================================================

    candidates = select_balanced_candidates(
        passed_ai
    )

    # ========================================================
    # DISTRIBUZIONI
    # ========================================================

    category_distribution = Counter(
        item.get(
            "category",
            "Tecnologia"
        )
        for item in candidates
    )

    story_type_distribution = Counter(
        item.get(
            "story_type",
            "NEWS"
        )
        for item in candidates
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    output = {
        "generated_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime()
        ),

        "collector_version": data.get(
            "version",
            data.get(
                "collector_version",
                "2.4"
            )
        ),

        "filter_version": VERSION,

        "model": MODEL,

        "total_received": len(items),

        "total_analyzed": len(analyzed),

        "total_passed_ai": len(passed_ai),

        "total_final_candidates": len(
            candidates
        ),

        "category_distribution": dict(
            category_distribution
        ),

        "story_type_distribution": dict(
            story_type_distribution
        ),

        "exclusion_summary": dict(
            exclusion_counter
        ),

        "items": candidates,

        "all_analyzed": analyzed
    }

    save_json(
        OUTPUT_FILE,
        output
    )

    # ========================================================
    # RISULTATO
    # ========================================================

    print("")
    print("======================================")
    print("       RISULTATO AI VISION 2.6")
    print("======================================")

    print(
        f"Articoli ricevuti: {len(items)}"
    )

    print(
        f"Articoli analizzati: {len(analyzed)}"
    )

    print(
        f"Approvati dall'AI: {len(passed_ai)}"
    )

    print(
        f"Candidati finali: {len(candidates)}"
    )

    print("")

    # ========================================================
    # ESCLUSIONI
    # ========================================================

    print("ESCLUSIONI")
    print("--------------------------------------")

    if exclusion_counter:

        for reason, count in (
            exclusion_counter.most_common()
        ):
            print(
                f"- {reason}: {count}"
            )

    else:

        print(
            "- Nessuna esclusione"
        )

    print("")

    # ========================================================
    # CATEGORIE
    # ========================================================

    print("DISTRIBUZIONE CATEGORIE")
    print("--------------------------------------")

    if category_distribution:

        for category, count in (
            category_distribution.most_common()
        ):
            print(
                f"- {category}: {count}"
            )

    else:

        print(
            "- Nessuna categoria"
        )

    print("")

    # ========================================================
    # CANDIDATI
    # ========================================================

    print("CANDIDATI FINALI")
    print("--------------------------------------")

    for index, item in enumerate(
        candidates,
        1
    ):

        ai = item.get(
            "ai",
            {}
        )

        print(
            f"{index}. "
            f"[{item.get('final_score', 0)}] "
            f"{item.get('title', '')}"
        )

        print(
            f"   Categoria: "
            f"{item.get('category', 'N/D')}"
        )

        print(
            f"   Tipo: "
            f"{item.get('story_type', 'N/D')}"
        )

        print(
            f"   Collector score: "
            f"{item.get('score', 0)}"
        )

        print(
            f"   AI score: "
            f"{ai.get('score', 0)}"
        )

        print(
            f"   Valore lettore: "
            f"{ai.get('reader_value', 0)}"
        )

        print(
            f"   Rilevanza Italia: "
            f"{ai.get('italian_relevance', 0)}"
        )

        print(
            f"   Originalità: "
            f"{ai.get('originality_potential', 0)}"
        )

        print(
            f"   Valore commerciale: "
            f"{ai.get('commercial_value', 0)}"
        )

        print(
            f"   Urgenza: "
            f"{ai.get('urgency', 0)}"
        )

        print(
            f"   Motivo: "
            f"{ai.get('reason', '')}"
        )

        print("")

    print("======================================")
    print(
        f"Output salvato in: {OUTPUT_FILE}"
    )
    print("======================================")


if __name__ == "__main__":
    main()
