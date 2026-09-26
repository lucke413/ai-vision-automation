#!/usr/bin/env python3

"""
AI Vision - AI Filter 2.4

Legge gli articoli prodotti dal RSS Collector 2.4,
li sottopone a Gemini e decide quali possono diventare
articoli per AI Vision.

Il Collector assegna già:
- category
- story_type
- editorial_score
- cluster
- source
- entities

Gemini NON deve riclassificare la notizia.

NON pubblica nulla.
NON modifica WordPress.

Produce:
    data/ai_candidates.json
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

INPUT_FILE = Path("data/rss_output.json")
OUTPUT_FILE = Path("data/ai_candidates.json")

MODEL = "gemini-3.5-flash-lite"

# Il Collector 2.4 prepara fino a 80 articoli.
MAX_AI_ITEMS = 80

# Pausa tra richieste Gemini.
REQUEST_DELAY = 1.0

# Punteggio minimo AI per considerare una storia
# potenzialmente pubblicabile.
MIN_AI_SCORE = 55

# Punteggio finale minimo.
MIN_FINAL_SCORE = 60

# Massimo numero di candidati che possono essere
# effettivamente passati allo step successivo.
MAX_CANDIDATES = 20

# Limite AI per evitare che il sito venga dominato
# dalle notizie di intelligenza artificiale.
MAX_AI_CANDIDATES = 6


# ============================================================
# CLIENT GEMINI
# ============================================================

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY non presente nelle variabili d'ambiente."
    )

client = genai.Client(
    api_key=api_key
)


# ============================================================
# CATEGORIE AMMESSE
# ============================================================

VALID_CATEGORIES = {
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
}


VALID_STORY_TYPES = {
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


# ============================================================
# PROMPT GEMINI
# ============================================================

SYSTEM_PROMPT = """
Sei il responsabile editoriale automatico di AI Vision,
una rivista italiana generalista dedicata alla tecnologia
consumer e digitale.

AI Vision tratta:

- smartphone e mobile
- PC e hardware
- gaming
- software e app
- intelligenza artificiale
- sicurezza informatica
- gadget e tecnologia consumer
- streaming e intrattenimento
- offerte e prezzi
- tecnologia e innovazione

OBIETTIVO

Devi stabilire se una notizia RSS è abbastanza interessante,
concreta e utile da diventare un articolo originale per AI Vision.

IMPORTANTE:

La categoria e il tipo di storia sono stati assegnati
precedentemente dal RSS Collector.

NON devi cambiarli.

NON devi inventare una nuova categoria.

NON devi trasformare una notizia in AI solo perché contiene
una parola relativa all'intelligenza artificiale.

Il sito deve rimanere GENERALISTA.

VALUTA SOPRATTUTTO:

1. Novità concreta.
2. Utilità per il lettore.
3. Interesse per un pubblico italiano.
4. Possibilità di creare un articolo originale.
5. Presenza di informazioni verificabili.
6. Interesse pratico o commerciale quando appropriato.
7. Rilevanza del prodotto, servizio o tecnologia.
8. Attualità.
9. Possibilità di spiegare il tema senza limitarsi
   a riscrivere la fonte.

SONO POSITIVE:

- nuovi prodotti
- aggiornamenti importanti
- nuove funzioni
- problemi che interessano molti utenti
- vulnerabilità e sicurezza
- guide pratiche
- recensioni
- confronti
- offerte realmente interessanti
- prezzi e disponibilità
- cambiamenti importanti di software e servizi
- novità gaming
- novità smartphone
- novità hardware
- innovazioni tecnologiche
- notizie AI con impatto concreto per gli utenti

SONO DA PENALIZZARE:

- comunicati aziendali privi di utilità per il lettore
- risultati finanziari
- dichiarazioni corporate senza conseguenze concrete
- partnership puramente aziendali
- rumor deboli o non verificabili
- notizie estremamente speculative
- contenuti troppo tecnici senza utilità pratica
- duplicati
- notizie banali
- articoli il cui unico elemento interessante è il nome
  di una grande azienda
- contenuti promozionali privi di informazioni utili

NOTA IMPORTANTE SULL'AI

AI è una categoria del sito, ma NON è il tema dominante.

Una notizia AI deve avere un motivo concreto per essere
pubblicata.

Ad esempio:

- nuova funzione ChatGPT utilizzabile dagli utenti
- nuova funzione Gemini
- nuovo strumento AI realmente disponibile
- importante aggiornamento di un servizio
- nuova tecnologia AI con impatto pratico
- sicurezza legata all'AI
- prodotto consumer basato su AI

Una semplice dichiarazione aziendale sull'AI
non è automaticamente interessante.

OUTPUT

Restituisci esclusivamente JSON valido.

Usa questo schema:

{
  "publishable": true,
  "score": 0,
  "reason": "",
  "italian_relevance": 0,
  "originality_potential": 0,
  "reader_value": 0,
  "urgency": 0,
  "commercial_value": 0,
  "format": ""
}

DOVE:

publishable:
true oppure false

score:
0-100

italian_relevance:
0-100

originality_potential:
0-100

reader_value:
0-100

urgency:
0-100

commercial_value:
0-100

reason:
motivazione breve e concreta

format:
breve descrizione del possibile articolo.
NON scrivere l'articolo.

NON restituire category.
NON restituire story_type.
NON modificarli.
"""


def build_prompt(item: dict) -> str:

    category = item.get(
        "category",
        "Tecnologia",
    )

    story_type = item.get(
        "story_type",
        "NEWS",
    )

    if category not in VALID_CATEGORIES:
        category = "Tecnologia"

    if story_type not in VALID_STORY_TYPES:
        story_type = "NEWS"

    entities = item.get(
        "entities",
        [],
    )

    sources = item.get(
        "sources",
        [],
    )

    cluster_articles = item.get(
        "cluster_articles",
        [],
    )

    return f"""
{SYSTEM_PROMPT}

============================================================
DATI DEL COLLECTOR
============================================================

Categoria assegnata dal Collector:
{category}

Tipo di storia assegnato dal Collector:
{story_type}

Punteggio editoriale Collector:
{item.get("editorial_score", 0)}

Numero fonti nel cluster:
{item.get("source_count", 1)}

Numero articoli nel cluster:
{item.get("article_count", 1)}

Entità rilevate:
{", ".join(entities)}

Fonti del cluster:
{", ".join(sources)}

Articoli presenti nel cluster:
{json.dumps(cluster_articles, ensure_ascii=False)}

============================================================
ARTICOLO
============================================================

Fonte:
{item.get("source", "")}

Titolo:
{item.get("title", "")}

Descrizione:
{item.get("description", "")}

URL:
{item.get("url", "")}

Data:
{item.get("published", "")}

============================================================

Valuta esclusivamente la qualità editoriale della notizia.

NON cambiare:

Categoria:
{category}

Tipo:
{story_type}

Rispondi esclusivamente con JSON valido:

{{
  "publishable": true,
  "score": 0,
  "reason": "",
  "italian_relevance": 0,
  "originality_potential": 0,
  "reader_value": 0,
  "urgency": 0,
  "commercial_value": 0,
  "format": ""
}}
"""


# ============================================================
# JSON PARSING
# ============================================================

def parse_json_response(text: str) -> dict:

    if not text:
        raise ValueError(
            "Risposta Gemini vuota."
        )

    text = text.strip()

    # Elimina eventuali code fence.
    if text.startswith("```"):
        text = text.replace(
            "```json",
            "",
            1,
        )

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:

        # Tentativo di recuperare il primo oggetto JSON
        # se Gemini ha aggiunto testo prima/dopo.
        start = text.find("{")
        end = text.rfind("}")

        if start >= 0 and end > start:
            candidate = text[
                start:end + 1
            ]

            return json.loads(candidate)

        raise


# ============================================================
# NORMALIZZAZIONE RISULTATO AI
# ============================================================

def normalize_ai_result(result: dict) -> dict:

    def number(
        key: str,
        default: int = 0,
    ) -> int:

        value = result.get(
            key,
            default,
        )

        try:
            value = int(value)
        except (
            TypeError,
            ValueError,
        ):
            value = default

        return max(
            0,
            min(100, value),
        )

    publishable = result.get(
        "publishable",
        False,
    )

    if not isinstance(
        publishable,
        bool,
    ):
        publishable = str(
            publishable
        ).lower() == "true"

    return {
        "publishable": publishable,

        "score": number(
            "score"
        ),

        "reason": str(
            result.get(
                "reason",
                "",
            )
        ).strip(),

        "italian_relevance": number(
            "italian_relevance"
        ),

        "originality_potential": number(
            "originality_potential"
        ),

        "reader_value": number(
            "reader_value"
        ),

        "urgency": number(
            "urgency"
        ),

        "commercial_value": number(
            "commercial_value"
        ),

        "format": str(
            result.get(
                "format",
                "",
            )
        ).strip(),
    }


# ============================================================
# GEMINI ANALYSIS
# ============================================================

def analyze_item(item: dict) -> dict:

    prompt = build_prompt(
        item
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    result = parse_json_response(
        response.text
    )

    return normalize_ai_result(
        result
    )


# ============================================================
# FINAL SCORE
# ============================================================

def calculate_final_score(
    item: dict,
    ai_result: dict,
) -> int:

    collector_score = int(
        item.get(
            "editorial_score",
            0,
        )
    )

    ai_score = int(
        ai_result.get(
            "score",
            0,
        )
    )

    reader_value = int(
        ai_result.get(
            "reader_value",
            0,
        )
    )

    italian_relevance = int(
        ai_result.get(
            "italian_relevance",
            0,
        )
    )

    originality = int(
        ai_result.get(
            "originality_potential",
            0,
        )
    )

    commercial_value = int(
        ai_result.get(
            "commercial_value",
            0,
        )
    )

    urgency = int(
        ai_result.get(
            "urgency",
            0,
        )
    )

    # Il Collector resta il principale filtro editoriale.
    final_score = (
        collector_score * 0.35
        + ai_score * 0.25
        + reader_value * 0.15
        + italian_relevance * 0.10
        + originality * 0.05
        + commercial_value * 0.05
        + urgency * 0.05
    )

    return max(
        0,
        min(
            100,
            round(final_score),
        ),
    )


# ============================================================
# HARD FILTER
# ============================================================

def apply_hard_rules(
    item: dict,
    ai_result: dict,
) -> tuple[bool, str]:

    category = item.get(
        "category",
        "Tecnologia",
    )

    story_type = item.get(
        "story_type",
        "NEWS",
    )

    collector_score = int(
        item.get(
            "editorial_score",
            0,
        )
    )

    ai_score = int(
        ai_result.get(
            "score",
            0,
        )
    )

    reader_value = int(
        ai_result.get(
            "reader_value",
            0,
        )
    )

    # Gemini deve esplicitamente approvare.
    if not ai_result.get(
        "publishable",
        False,
    ):
        return (
            False,
            "Gemini ha classificato la notizia come non pubblicabile.",
        )

    # AI score troppo basso.
    if ai_score < MIN_AI_SCORE:
        return (
            False,
            f"AI score troppo basso ({ai_score}).",
        )

    # Collector score troppo basso.
    if collector_score < 45:
        return (
            False,
            f"Collector score troppo basso ({collector_score}).",
        )

    # Il contenuto deve avere almeno un minimo
    # di valore per il lettore.
    if reader_value < 45:
        return (
            False,
            f"Reader value troppo basso ({reader_value}).",
        )

    # Rumor: soglia più alta.
    if story_type == "RUMOR":
        if ai_score < 75:
            return (
                False,
                "Rumor con punteggio insufficiente.",
            )

    # Aziendale puro: soglia molto alta.
    if story_type == "AZIENDALE":
        if ai_score < 75:
            return (
                False,
                "Contenuto aziendale con valore editoriale insufficiente.",
            )

    # Le offerte devono avere reale componente commerciale.
    if category == "Offerte & Prezzi":
        commercial_value = int(
            ai_result.get(
                "commercial_value",
                0,
            )
        )

        if commercial_value < 50:
            return (
                False,
                "Offerta con valore commerciale insufficiente.",
            )

    return (
        True,
        "Supera i filtri editoriali.",
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # INPUT
    # --------------------------------------------------------

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"File non trovato: {INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    items = data.get(
        "items",
        [],
    )

    # Il Collector decide già quanti articoli passare.
    items = items[:MAX_AI_ITEMS]

    print("")
    print("=" * 70)
    print("              AI VISION - AI FILTER 2.4")
    print("=" * 70)
    print("")
    print(
        f"Articoli ricevuti dal Collector: "
        f"{len(items)}"
    )

    print(
        f"Massimo articoli analizzati: "
        f"{MAX_AI_ITEMS}"
    )

    print("")

    # --------------------------------------------------------
    # ANALISI
    # --------------------------------------------------------

    analyzed = []

    for number, item in enumerate(
        items,
        start=1,
    ):

        title = item.get(
            "title",
            "",
        )

        category = item.get(
            "category",
            "Tecnologia",
        )

        story_type = item.get(
            "story_type",
            "NEWS",
        )

        print(
            f"[{number}/{len(items)}] "
            f"[{category}] "
            f"[{story_type}] "
            f"{title}"
        )

        try:

            ai_result = analyze_item(
                item
            )

            final_score = calculate_final_score(
                item,
                ai_result,
            )

            passes_rules, rule_reason = (
                apply_hard_rules(
                    item,
                    ai_result,
                )
            )

            combined = {
                **item,

                "ai": {
                    **ai_result,

                    # Manteniamo esplicitamente
                    # la classificazione Collector.
                    "collector_category": category,

                    "collector_story_type": story_type,

                    "collector_score": item.get(
                        "editorial_score",
                        0,
                    ),

                    "final_score": final_score,

                    "passes_rules": passes_rules,

                    "rule_reason": rule_reason,
                },
            }

            analyzed.append(
                combined
            )

            print(
                f"    Collector: "
                f"{item.get('editorial_score', 0)}"
            )

            print(
                f"    Gemini: "
                f"{ai_result.get('score', 0)}"
            )

            print(
                f"    Final: "
                f"{final_score}"
            )

            print(
                f"    Pubblicabile AI: "
                f"{ai_result.get('publishable', False)}"
            )

            print(
                f"    Filtri: "
                f"{passes_rules}"
            )

            print(
                f"    Motivo: "
                f"{ai_result.get('reason', '')}"
            )

        except Exception as exc:

            print(
                f"    ERRORE GEMINI: {exc}"
            )

            analyzed.append(
                {
                    **item,

                    "ai": {
                        "publishable": False,
                        "score": 0,
                        "reason": (
                            f"Errore AI: {exc}"
                        ),
                        "italian_relevance": 0,
                        "originality_potential": 0,
                        "reader_value": 0,
                        "urgency": 0,
                        "commercial_value": 0,
                        "format": "",
                        "collector_category": category,
                        "collector_story_type": story_type,
                        "collector_score": item.get(
                            "editorial_score",
                            0,
                        ),
                        "final_score": 0,
                        "passes_rules": False,
                        "rule_reason": (
                            "Errore durante analisi Gemini."
                        ),
                    },
                }
            )

        # Pausa tra richieste.
        if number < len(items):
            time.sleep(
                REQUEST_DELAY
            )

    # --------------------------------------------------------
    # CANDIDATI
    # --------------------------------------------------------

    candidates = [
        item
        for item in analyzed
        if item.get(
            "ai",
            {}
        ).get(
            "passes_rules",
            False,
        )
        and item.get(
            "ai",
            {}
        ).get(
            "final_score",
            0,
        ) >= MIN_FINAL_SCORE
    ]

    # --------------------------------------------------------
    # ORDINAMENTO
    # --------------------------------------------------------

    candidates.sort(
        key=lambda item: (
            item.get(
                "ai",
                {}
            ).get(
                "final_score",
                0,
            ),

            item.get(
                "editorial_score",
                0,
            ),

            item.get(
                "source_count",
                1,
            ),
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # LIMITE AI
    # --------------------------------------------------------

    final_candidates = []

    ai_count = 0

    for item in candidates:

        category = item.get(
            "category",
            "Tecnologia",
        )

        if category == "AI":

            if ai_count >= MAX_AI_CANDIDATES:
                continue

            ai_count += 1

        if len(final_candidates) >= MAX_CANDIDATES:
            break

        final_candidates.append(
            item
        )

    # --------------------------------------------------------
    # STATISTICHE
    # --------------------------------------------------------

    category_distribution = {}

    for item in final_candidates:

        category = item.get(
            "category",
            "Tecnologia",
        )

        category_distribution[
            category
        ] = (
            category_distribution.get(
                category,
                0,
            )
            + 1
        )

    story_type_distribution = {}

    for item in final_candidates:

        story_type = item.get(
            "story_type",
            "NEWS",
        )

        story_type_distribution[
            story_type
        ] = (
            story_type_distribution.get(
                story_type,
                0,
            )
            + 1
        )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "generated_at": (
            data.get(
                "collector",
                {},
            ).get(
                "generated_at"
            )
            or data.get(
                "generated_at"
            )
        ),

        "collector_version": data.get(
            "collector",
            {},
        ).get(
            "version",
            "unknown",
        ),

        "model": MODEL,

        "total_received": len(items),

        "total_analyzed": len(analyzed),

        "total_passed_ai": len(candidates),

        "total_final_candidates": len(
            final_candidates
        ),

        "category_distribution": (
            category_distribution
        ),

        "story_type_distribution": (
            story_type_distribution
        ),

        "items": final_candidates,

        # Utile per debugging e analisi.
        "all_analyzed": analyzed,
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

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    print("")
    print("=" * 70)
    print("                 FILTRO COMPLETATO")
    print("=" * 70)

    print(
        f"Ricevuti dal Collector: "
        f"{len(items)}"
    )

    print(
        f"Analizzati da Gemini: "
        f"{len(analyzed)}"
    )

    print(
        f"Passati filtri AI: "
        f"{len(candidates)}"
    )

    print(
        f"Candidati finali: "
        f"{len(final_candidates)}"
    )

    print("")
    print("DISTRIBUZIONE CATEGORIE")
    print("-" * 70)

    for category, count in sorted(
        category_distribution.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(
            f"{category:<32} {count:>3}"
        )

    print("")
    print("DISTRIBUZIONE TIPI")
    print("-" * 70)

    for story_type, count in sorted(
        story_type_distribution.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(
            f"{story_type:<32} {count:>3}"
        )

    print("")
    print("CANDIDATI FINALI")
    print("-" * 70)

    for index, item in enumerate(
        final_candidates,
        start=1,
    ):

        ai = item.get(
            "ai",
            {},
        )

        print(
            f"{index:>2}. "
            f"[{ai.get('final_score', 0):>3}] "
            f"[{item.get('category', '')}] "
            f"[{item.get('story_type', '')}] "
            f"{item.get('title', '')}"
        )

        print(
            f"    Fonte: "
            f"{item.get('source', '')}"
        )

        print(
            f"    Motivazione: "
            f"{ai.get('reason', '')}"
        )

    print("")
    print(
        f"File: {OUTPUT_FILE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
