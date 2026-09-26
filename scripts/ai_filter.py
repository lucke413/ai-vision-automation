import json
import os
import time
from pathlib import Path
from collections import Counter

import requests


# ============================================================
# AI VISION - AI FILTER 2.5
# ============================================================

VERSION = "2.5"

INPUT_FILE = Path("data/rss_output.json")
OUTPUT_FILE = Path("data/ai_candidates.json")

MODEL = "gemini-3.5-flash-lite"

MAX_AI_ITEMS = 80
MAX_CANDIDATES = 20
MAX_AI_CANDIDATES = 6

REQUEST_DELAY = 1.0

MIN_AI_SCORE = 55
MIN_FINAL_SCORE = 60

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)


# ============================================================
# LIMITI EDITORIALI
# ============================================================

CATEGORY_LIMITS = {
    "Offerte & Prezzi": 3,
    "Sicurezza": 4,
    "Smartphone & Mobile": 6,
    "PC & Hardware": 4,
    "Gaming": 4,
    "Software & App": 4,
    "AI": 4,
    "Gadget & Consumer Tech": 4,
    "Streaming & Entertainment": 3,
    "Tecnologia": 4,
}

# Preferenza editoriale.
# Non sono obblighi assoluti: servono per evitare una selezione
# dominata da una sola categoria.
CATEGORY_PRIORITY = {
    "Smartphone & Mobile": 1.00,
    "PC & Hardware": 1.00,
    "Gaming": 0.95,
    "Software & App": 0.95,
    "Sicurezza": 1.00,
    "AI": 0.90,
    "Gadget & Consumer Tech": 0.90,
    "Streaming & Entertainment": 0.85,
    "Offerte & Prezzi": 0.70,
    "Tecnologia": 0.85,
}


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
            indent=2,
        )


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
    Estrae il primo oggetto JSON valido dalla risposta Gemini.
    """

    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON Gemini non trovato")

    return json.loads(text[start:end + 1])


# ============================================================
# GEMINI
# ============================================================

def ask_gemini(item, api_key):
    title = normalize_text(item.get("title"))
    description = normalize_text(
        item.get("description")
        or item.get("summary")
        or item.get("content")
    )

    category = normalize_text(item.get("category"))
    story_type = normalize_text(item.get("story_type"))
    source = normalize_text(item.get("source"))

    prompt = f"""
Sei il responsabile editoriale di AI Vision, magazine tecnologico italiano
generalista rivolto a lettori consumer.

Il magazine tratta:
- smartphone e mobile
- PC e hardware
- gaming
- software e app
- intelligenza artificiale
- sicurezza informatica
- gadget e tecnologia consumer
- streaming e intrattenimento
- offerte e prezzi
- tecnologia generale

L'AI NON deve diventare la categoria dominante.

La classificazione preliminare del Collector è:
Categoria: {category}
Tipo: {story_type}

Titolo:
{title}

Fonte:
{source}

Descrizione:
{description}

Valuta se questa notizia merita di entrare nella pipeline editoriale.

IMPORTANTE:

1. Non inventare informazioni.
2. Non cambiare arbitrariamente categoria e story_type del Collector.
3. Tuttavia, segnala se la classificazione appare palesemente incoerente.
4. Una normale problematica Windows, Android, iOS o software NON è automaticamente
   un problema di sicurezza.
5. Una recensione deve essere realmente una recensione.
6. Un'offerta deve avere un valore commerciale concreto.
7. Evita contenuti puramente aziendali, comunicati stampa e marketing.
8. Considera il valore per un lettore italiano.
9. Considera originalità e possibilità di realizzare un articolo originale.
10. Evita notizie troppo generiche o poco utili.
11. Rumor e indiscrezioni richiedono una soglia più alta.
12. Le offerte non devono essere considerate automaticamente più importanti
    delle news, guide, sicurezza o recensioni.
13. Se il titolo parla di un prodotto ma non c'è una vera offerta,
    non considerarlo un'offerta solo perché il prodotto è acquistabile.

Restituisci SOLO JSON valido con questa struttura:

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

Punteggi da 0 a 100.

FORMAT può essere uno tra:
NEWS
GUIDA
RECENSIONE
SICUREZZA
OFFERTA
ANALISI
RUMOR

Se non c'è un problema evidente di classificazione:
"classification_issue": false
"suggested_category": ""
"suggested_story_type": ""

Se invece la classificazione è palesemente sbagliata,
indica la classificazione corretta nei due campi suggested_*.
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
        timeout=90,
    )

    response.raise_for_status()

    data = response.json()

    text = (
        data["candidates"][0]["content"]["parts"][0]["text"]
    )

    return extract_json(text)


# ============================================================
# CLASSIFICAZIONE
# ============================================================

def correct_classification(item, ai):
    """
    Corregge solo errori evidenti.
    Il Collector rimane la classificazione principale.
    """

    category = item.get("category", "Tecnologia")
    story_type = item.get("story_type", "NEWS")

    if not ai.get("classification_issue"):
        return category, story_type

    suggested_category = normalize_text(
        ai.get("suggested_category")
    )

    suggested_story_type = normalize_text(
        ai.get("suggested_story_type")
    )

    valid_categories = set(CATEGORY_LIMITS.keys())

    valid_types = {
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

    if suggested_category in valid_categories:
        category = suggested_category

    if suggested_story_type in valid_types:
        story_type = suggested_story_type

    return category, story_type


# ============================================================
# SCORE
# ============================================================

def calculate_final_score(item, ai):
    collector_score = clamp(item.get("score", 0))
    ai_score = clamp(ai.get("score", 0))

    reader_value = clamp(ai.get("reader_value", 0))
    italian_relevance = clamp(ai.get("italian_relevance", 0))
    originality = clamp(ai.get("originality_potential", 0))
    commercial_value = clamp(ai.get("commercial_value", 0))
    urgency = clamp(ai.get("urgency", 0))

    final_score = (
        collector_score * 0.35
        + ai_score * 0.25
        + reader_value * 0.15
        + italian_relevance * 0.10
        + originality * 0.05
        + commercial_value * 0.05
        + urgency * 0.05
    )

    category = item.get("category", "")

    # Piccolo correttivo editoriale.
    # Non cambia radicalmente il punteggio ma evita che le offerte
    # vincano semplicemente grazie al valore commerciale.
    priority = CATEGORY_PRIORITY.get(category, 0.85)

    final_score *= priority

    # Le offerte devono avere reale valore commerciale.
    if item.get("story_type") == "OFFERTA":
        if commercial_value < 50:
            final_score -= 8

    # I rumor richiedono maggiore prudenza.
    if item.get("story_type") == "RUMOR":
        if ai_score < 75:
            final_score -= 10

    # Aziendale: soglia molto alta.
    if item.get("story_type") == "AZIENDALE":
        if ai_score < 75:
            final_score -= 12

    return round(clamp(final_score), 2)


# ============================================================
# FILTRI
# ============================================================

def passes_hard_rules(item, ai):
    if not ai.get("publishable", False):
        return False

    ai_score = clamp(ai.get("score", 0))
    collector_score = clamp(item.get("score", 0))
    reader_value = clamp(ai.get("reader_value", 0))

    if ai_score < MIN_AI_SCORE:
        return False

    if collector_score < 45:
        return False

    if reader_value < 45:
        return False

    story_type = item.get("story_type")

    if story_type == "RUMOR" and ai_score < 75:
        return False

    if story_type == "AZIENDALE" and ai_score < 75:
        return False

    if story_type == "OFFERTA":
        commercial_value = clamp(
            ai.get("commercial_value", 0)
        )

        if commercial_value < 50:
            return False

    return True


# ============================================================
# SELEZIONE BILANCIATA
# ============================================================

def select_balanced_candidates(items):
    """
    Seleziona massimo MAX_CANDIDATES articoli rispettando i limiti
    per categoria.

    Prima considera il punteggio, ma evita che una singola categoria
    occupi tutto il risultato.
    """

    sorted_items = sorted(
        items,
        key=lambda x: x.get("final_score", 0),
        reverse=True,
    )

    selected = []
    category_counts = Counter()

    # --------------------------------------------------------
    # Primo passaggio:
    # prendiamo il migliore di ogni categoria disponibile.
    # --------------------------------------------------------

    categories_seen = set()

    for item in sorted_items:
        category = item.get("category", "Tecnologia")

        if category in categories_seen:
            continue

        if len(selected) >= MAX_CANDIDATES:
            break

        limit = CATEGORY_LIMITS.get(category, 3)

        if limit <= 0:
            continue

        selected.append(item)
        category_counts[category] += 1
        categories_seen.add(category)

    # --------------------------------------------------------
    # Secondo passaggio:
    # completiamo la lista con i punteggi migliori,
    # rispettando i limiti.
    # --------------------------------------------------------

    for item in sorted_items:
        if len(selected) >= MAX_CANDIDATES:
            break

        if item in selected:
            continue

        category = item.get("category", "Tecnologia")
        limit = CATEGORY_LIMITS.get(category, 3)

        if category_counts[category] >= limit:
            continue

        selected.append(item)
        category_counts[category] += 1

    # --------------------------------------------------------
    # Ordinamento finale.
    # --------------------------------------------------------

    selected.sort(
        key=lambda x: x.get("final_score", 0),
        reverse=True,
    )

    return selected


# ============================================================
# MAIN
# ============================================================

def main():
    print("======================================")
    print("       AI VISION - AI FILTER 2.5")
    print("======================================")

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY non configurata"
        )

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"File non trovato: {INPUT_FILE}"
        )

    data = load_json(INPUT_FILE)

    items = data.get("items", [])

    if not items:
        raise RuntimeError(
            "Nessun articolo trovato in rss_output.json"
        )

    # --------------------------------------------------------
    # Limite articoli inviati a Gemini
    # --------------------------------------------------------

    items = items[:MAX_AI_ITEMS]

    print(f"Articoli ricevuti: {len(items)}")
    print(f"Modello: {MODEL}")
    print("")

    analyzed = []
    passed_ai = []

    # --------------------------------------------------------
    # Analisi Gemini
    # --------------------------------------------------------

    for index, item in enumerate(items, 1):

        print(
            f"[{index}/{len(items)}] "
            f"{item.get('title', '')}"
        )

        try:
            ai = ask_gemini(
                item,
                api_key,
            )

        except Exception as exc:
            print(
                f"   ERRORE Gemini: {exc}"
            )

            item_copy = dict(item)

            item_copy["ai"] = {
                "publishable": False,
                "score": 0,
                "reason": f"Errore Gemini: {exc}",
            }

            item_copy["final_score"] = 0

            analyzed.append(item_copy)

            time.sleep(REQUEST_DELAY)
            continue

        # ----------------------------------------------------
        # Correzione classificazione evidente
        # ----------------------------------------------------

        corrected_category, corrected_story_type = (
            correct_classification(
                item,
                ai,
            )
        )

        item_copy = dict(item)

        item_copy["category"] = corrected_category
        item_copy["story_type"] = corrected_story_type

        item_copy["ai"] = ai

        # ----------------------------------------------------
        # Hard rules
        # ----------------------------------------------------

        accepted = passes_hard_rules(
            item_copy,
            ai,
        )

        # ----------------------------------------------------
        # Final score
        # ----------------------------------------------------

        final_score = calculate_final_score(
            item_copy,
            ai,
        )

        item_copy["final_score"] = final_score

        # ----------------------------------------------------
        # Approvazione
        # ----------------------------------------------------

        if accepted and final_score >= MIN_FINAL_SCORE:
            item_copy["ai"]["publishable"] = True
            passed_ai.append(item_copy)

        else:
            item_copy["ai"]["publishable"] = False

        analyzed.append(item_copy)

        time.sleep(REQUEST_DELAY)

    # --------------------------------------------------------
    # Selezione bilanciata
    # --------------------------------------------------------

    candidates = select_balanced_candidates(
        passed_ai
    )

    # --------------------------------------------------------
    # Distribuzioni
    # --------------------------------------------------------

    category_distribution = Counter(
        item.get("category", "Tecnologia")
        for item in candidates
    )

    story_type_distribution = Counter(
        item.get("story_type", "NEWS")
        for item in candidates
    )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    output = {
        "generated_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
        "collector_version": data.get(
            "version",
            data.get("collector_version", "2.4"),
        ),
        "filter_version": VERSION,
        "model": MODEL,

        "total_received": len(items),
        "total_analyzed": len(analyzed),
        "total_passed_ai": len(passed_ai),
        "total_final_candidates": len(candidates),

        "category_distribution": dict(
            category_distribution
        ),

        "story_type_distribution": dict(
            story_type_distribution
        ),

        "items": candidates,

        "all_analyzed": analyzed,
    }

    save_json(
        OUTPUT_FILE,
        output,
    )

    # --------------------------------------------------------
    # Risultato console
    # --------------------------------------------------------

    print("")
    print("======================================")
    print("       SELEZIONE COMPLETATA")
    print("======================================")

    print(
        f"Articoli analizzati: "
        f"{len(analyzed)}"
    )

    print(
        f"Approvati dall'AI: "
        f"{len(passed_ai)}"
    )

    print(
        f"Candidati finali: "
        f"{len(candidates)}"
    )

    print("")
    print("DISTRIBUZIONE CATEGORIE")

    for category, count in category_distribution.most_common():
        print(
            f"- {category}: {count}"
        )

    print("")
    print("CANDIDATI FINALI")

    for index, item in enumerate(
        candidates,
        1,
    ):
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

        ai = item.get("ai", {})

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
