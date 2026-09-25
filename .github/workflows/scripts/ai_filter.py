#!/usr/bin/env python3

"""
AI Vision - AI Filter

Legge gli articoli raccolti dal RSS Collector,
li sottopone a Gemini e decide quali sono
interessanti per AI Vision.

NON pubblica nulla.
NON modifica WordPress.
Produce solamente data/ai_candidates.json.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from google import genai


# ============================================================
# CONFIGURAZIONE
# ============================================================

INPUT_FILE = Path("data/rss_items.json")
OUTPUT_FILE = Path("data/ai_candidates.json")

MODEL = "gemini-3.5-flash-lite"

MAX_AI_ITEMS = 31


# ============================================================
# CLIENT GEMINI
# ============================================================

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY non presente nelle variabili d'ambiente."
    )

client = genai.Client(api_key=api_key)


# ============================================================
# PROMPT
# ============================================================

SYSTEM_PROMPT = """
Sei il responsabile editoriale automatico di AI Vision,
un sito italiano dedicato a intelligenza artificiale,
tecnologia, strumenti digitali, sicurezza e prodotti.

Devi valutare una notizia RSS e stabilire se può diventare
un articolo originale e utile per AI Vision.

NON devi riscrivere la notizia.

Devi soltanto analizzarla.

CRITERI:

1. Deve essere recente o ancora rilevante.
2. Deve contenere una novità concreta.
3. Deve essere interessante per un pubblico italiano.
4. Deve poter essere trasformata in un articolo originale,
   senza copiare il testo della fonte.
5. Evita notizie banali, rumor non verificabili,
   comunicati privi di sostanza e contenuti duplicati.
6. Una notizia commerciale può essere accettata se contiene
   informazioni utili su prodotto, prezzo, disponibilità,
   caratteristiche o confronto.
7. Non considerare automaticamente interessante una notizia
   soltanto perché proviene da una fonte importante.

VALUTA:

- publishable: true/false
- score: da 0 a 100
- reason: breve motivazione
- category: una tra:
  News
  AI
  Tool e Servizi
  Tecnologia
  Sicurezza
  Guide
  Confronti
  Offerte
- format: descrizione breve del possibile articolo
- italian_relevance: da 0 a 100
- originality_potential: da 0 a 100
- urgency: da 0 a 100

Restituisci esclusivamente JSON valido.
"""


def build_prompt(item: dict) -> str:
    return f"""
{SYSTEM_PROMPT}

ARTICOLO DA VALUTARE

Fonte:
{item.get("source", "")}

Titolo:
{item.get("title", "")}

Descrizione:
{item.get("description", "")}

URL:
{item.get("url", "")}

Categoria suggerita dalla fonte:
{item.get("category_hint", "")}

Data:
{item.get("published_at", "")}

Rispondi esclusivamente con questo schema JSON:

{{
  "publishable": true,
  "score": 0,
  "reason": "",
  "category": "",
  "format": "",
  "italian_relevance": 0,
  "originality_potential": 0,
  "urgency": 0
}}
"""


# ============================================================
# ANALISI
# ============================================================

def analyze_item(item: dict) -> dict:

    prompt = build_prompt(item)

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    text = response.text.strip()

    # Rimuove eventuali code fence JSON.
    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    try:
        result = json.loads(text)

    except json.JSONDecodeError:

        return {
            "publishable": False,
            "score": 0,
            "reason": "Risposta AI non valida.",
            "category": "",
            "format": "",
            "italian_relevance": 0,
            "originality_potential": 0,
            "urgency": 0,
        }

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"File non trovato: {INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    items = data.get("items", [])

    items = items[:MAX_AI_ITEMS]

    print("")
    print("=" * 60)
    print("          AI VISION - AI FILTER")
    print("=" * 60)
    print("")
    print(f"Articoli da analizzare: {len(items)}")
    print("")

    candidates = []

    for number, item in enumerate(items, start=1):

        print(
            f"[{number}/{len(items)}] "
            f"{item.get('title', '')}"
        )

        try:

            result = analyze_item(item)

            combined = {
                **item,
                "ai": result,
            }

            candidates.append(combined)

            print(
                f"    Score: {result.get('score', 0)}"
            )

            print(
                f"    Pubblicabile: "
                f"{result.get('publishable', False)}"
            )

            print(
                f"    Categoria: "
                f"{result.get('category', '')}"
            )

        except Exception as exc:

            print(
                f"    ERRORE: {exc}"
            )

            candidates.append({
                **item,
                "ai": {
                    "publishable": False,
                    "score": 0,
                    "reason": f"Errore AI: {exc}",
                    "category": "",
                    "format": "",
                    "italian_relevance": 0,
                    "originality_potential": 0,
                    "urgency": 0,
                },
            })

        # Piccola pausa per evitare richieste troppo ravvicinate.
        time.sleep(1)

    # ========================================================
    # ORDINAMENTO
    # ========================================================

    candidates.sort(
        key=lambda item: item.get("ai", {}).get(
            "score", 0
        ),
        reverse=True,
    )

    # ========================================================
    # SALVATAGGIO
    # ========================================================

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "generated_at": data.get(
            "generated_at"
        ),

        "model": MODEL,

        "total_analyzed": len(candidates),

        "publishable_candidates": sum(
            1
            for item in candidates
            if item.get("ai", {}).get(
                "publishable", False
            )
        ),

        "items": candidates,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("")
    print("=" * 60)
    print("              FILTRO COMPLETATO")
    print("=" * 60)
    print(
        f"Analizzati: {len(candidates)}"
    )
    print(
        f"Candidati: {output['publishable_candidates']}"
    )
    print(
        f"File: {OUTPUT_FILE}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
