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

MAX_ARTICLES_TO_ANALYZE = 80
MAX_FINAL_CANDIDATES = 20

REQUEST_DELAY = 1.0

# Soglie principali
MIN_AI_SCORE = 55
MIN_COLLECTOR_SCORE = 45
MIN_READER_VALUE = 45


# ============================================================
# LIMITI PER CATEGORIA
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
# HEADER
# ============================================================

print()
print("=" * 40)
print()
print("       AI VISION - AI FILTER 2.6")
print()
print("=" * 40)
print()
print("VERSIONE FILTRO:", VERSION)
print("MODELLO:", MODEL)
print("INPUT:", INPUT_FILE)
print("OUTPUT:", OUTPUT_FILE)
print()


# ============================================================
# LETTURA API KEY
# ============================================================

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if not API_KEY:
    print("ERRORE: GEMINI_API_KEY non presente.")
    raise SystemExit(1)


# ============================================================
# LETTURA RSS
# ============================================================

if not os.path.exists(INPUT_FILE):
    print(f"ERRORE: file non trovato: {INPUT_FILE}")
    raise SystemExit(1)

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    rss_data = json.load(f)


items = rss_data.get("items", [])

if not isinstance(items, list):
    print("ERRORE: il campo 'items' non contiene una lista.")
    raise SystemExit(1)


items = items[:MAX_ARTICLES_TO_ANALYZE]

print("Articoli ricevuti:", len(items))
print("Modello:", MODEL)
print()


# ============================================================
# URL GEMINI
# ============================================================

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    f"models/{MODEL}:generateContent"
    f"?key={API_KEY}"
)


# ============================================================
# FUNZIONI DI SUPPORTO
# ============================================================

def clean_text(value, max_length=4000):
    if value is None:
        return ""

    value = str(value)

    value = re.sub(r"\s+", " ", value)

    return value.strip()[:max_length]


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def normalize_category(category):
    if not category:
        return "Tecnologia"

    category = str(category).strip()

    aliases = {
        "Smartphone": "Smartphone & Mobile",
        "Mobile": "Smartphone & Mobile",
        "PC": "PC & Hardware",
        "Hardware": "PC & Hardware",
        "Software": "Software & App",
        "App": "Software & App",
        "AI & Machine Learning": "AI",
        "Artificial Intelligence": "AI",
        "Security": "Sicurezza",
        "Gadget": "Gadget & Consumer Tech",
        "Consumer Tech": "Gadget & Consumer Tech",
        "Streaming": "Streaming & Entertainment",
        "Entertainment": "Streaming & Entertainment",
        "Deals": "Offerte & Prezzi",
        "Offerte": "Offerte & Prezzi",
    }

    if category in aliases:
        category = aliases[category]

    if category not in CATEGORY_LIMITS:
        category = "Tecnologia"

    return category


def normalize_story_type(story_type):
    allowed = {
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

    story_type = str(story_type or "NEWS").strip().upper()

    if story_type not in allowed:
        return "NEWS"

    return story_type


# ============================================================
# PROMPT GEMINI
# ============================================================

def build_prompt(item):

    title = clean_text(
        item.get("title")
        or item.get("name")
        or "",
        500
    )

    description = clean_text(
        item.get("description")
        or item.get("summary")
        or "",
        2500
    )

    source = clean_text(
        item.get("source")
        or item.get("source_name")
        or "",
        300
    )

    category = clean_text(
        item.get("category")
        or "",
        100
    )

    story_type = clean_text(
        item.get("story_type")
        or "",
        100
    )

    collector_score = safe_int(
        item.get("score")
        or item.get("collector_score")
        or item.get("source_score")
        or 0
    )

    prompt = f"""
Sei il direttore editoriale di AI Vision, magazine italiano generalista dedicato alla tecnologia consumer.

Devi valutare una notizia proveniente da un feed RSS e stabilire se può diventare un articolo utile per AI Vision.

AI Vision tratta:
- smartphone e mobile
- PC e hardware
- gaming
- software e app
- intelligenza artificiale
- sicurezza
- gadget e tecnologia consumer
- streaming e entertainment
- offerte e prezzi
- tecnologia generale

IMPORTANTE:
AI Vision NON è un sito esclusivamente dedicato all'intelligenza artificiale.

Preferisci contenuti:
- utili al lettore italiano;
- concreti;
- interessanti per utenti consumer;
- con un possibile valore pratico;
- relativi a prodotti, servizi, software, sicurezza, gaming o tecnologia;
- con informazioni sufficienti per sviluppare un articolo originale.

Evita:
- comunicati aziendali puri;
- contenuti finanziari;
- risultati trimestrali;
- notizie esclusivamente corporate;
- contenuti troppo tecnici per un pubblico generalista;
- articoli privi di interesse pratico;
- notizie duplicate o estremamente simili a contenuti comuni;
- contenuti palesemente promozionali;
- rumor molto deboli;
- contenuti politici non pertinenti alla tecnologia.

Una notizia aziendale può essere accettata SOLO se ha un impatto concreto e interessante sulla tecnologia consumer.

Una notizia AI può essere accettata se ha un'utilità o un interesse concreto per il lettore. Non favorire automaticamente le notizie AI.

VALUTA:

1. publishable
   true/false

2. ai_score
   0-100
   Quanto la notizia è adatta editorialmente ad AI Vision.

3. reader_value
   0-100
   Quanto è utile/interessante per un lettore italiano.

4. italian_relevance
   0-100
   Quanto è rilevante per il pubblico italiano.

5. originality
   0-100
   Quanto offre un angolo editoriale interessante e non banale.

6. urgency
   0-100
   Quanto è importante pubblicarla rapidamente.

7. commercial_value
   0-100
   Possibile valore commerciale/affiliate/consumer.

8. format
   Scegli tra:
   NEWS
   GUIDA
   RECENSIONE
   OFFERTA
   SICUREZZA
   RUMOR
   SCIENZA
   ANALISI

9. suggested_category
   Deve essere una delle categorie:
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

10. suggested_story_type

11. classification_issue
   true/false

12. reason
   Breve motivazione in italiano.

REGOLE SPECIALI:

- Le offerte devono avere un reale interesse commerciale.
- I rumor devono essere trattati con cautela.
- Le notizie aziendali devono avere un impatto concreto sul lettore.
- Le notizie di sicurezza sono importanti se riguardano utenti, dispositivi, account, software o servizi realmente utilizzati.
- Una recensione può essere interessante anche se riguarda un prodotto di nicchia, purché abbia valore per il consumatore.
- Non classificare automaticamente un prodotto consumer come PC & Hardware solo perché contiene tecnologia.
- Accessori, utensili smart, periferiche, wearable e prodotti consumer devono essere valutati anche per Gadget & Consumer Tech.
- Non trasformare automaticamente ogni problema software in Sicurezza.
- Un problema Windows senza vulnerabilità, malware, attacco o rischio per la sicurezza deve normalmente rimanere Software & App o PC & Hardware.
- Non premiare automaticamente le notizie AI solo perché contengono la parola AI.

DATI DELLA NOTIZIA

Titolo:
{title}

Descrizione:
{description}

Fonte:
{source}

Categoria assegnata dal collector:
{category}

Tipo assegnato dal collector:
{story_type}

Punteggio collector:
{collector_score}

Rispondi ESCLUSIVAMENTE con JSON valido, senza markdown.

Formato:

{{
  "publishable": true,
  "ai_score": 0,
  "reader_value": 0,
  "italian_relevance": 0,
  "originality": 0,
  "urgency": 0,
  "commercial_value": 0,
  "format": "NEWS",
  "suggested_category": "Tecnologia",
  "suggested_story_type": "NEWS",
  "classification_issue": false,
  "reason": "..."
}}
"""

    return prompt


# ============================================================
# CHIAMATA GEMINI
# ============================================================

def call_gemini(prompt):

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

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(
        GEMINI_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    # ========================================================
    # DIAGNOSTICA SPECIFICA HTTP 429
    # ========================================================

    if response.status_code == 429:

        print()
        print("=" * 70)
        print("⚠️  GEMINI HTTP 429 - TOO MANY REQUESTS")
        print("=" * 70)

        print("Status:", response.status_code)

        print()
        print("HEADERS RILEVANTI:")

        found_header = False

        for key, value in response.headers.items():

            key_lower = key.lower()

            if key_lower in (
                "retry-after",
                "x-ratelimit-limit",
                "x-ratelimit-remaining",
                "x-ratelimit-reset"
            ):
                print(f"  {key}: {value}")
                found_header = True

        if not found_header:
            print("  Nessun header rate-limit disponibile.")

        print()
        print("RISPOSTA COMPLETA DI GEMINI:")

        try:
            error_json = response.json()

            print(
                json.dumps(
                    error_json,
                    indent=2,
                    ensure_ascii=False
                )
            )

        except Exception:
            print(response.text)

        print()
        print("=" * 70)
        print("FINE DIAGNOSTICA 429")
        print("=" * 70)
        print()

        raise RuntimeError(
            "Gemini ha restituito HTTP 429 - "
            "vedere diagnostica sopra."
        )

    # ========================================================
    # ALTRI ERRORI HTTP
    # ========================================================

    if response.status_code >= 400:

        print()
        print("=" * 70)
        print("ERRORE HTTP GEMINI")
        print("=" * 70)

        print("Status:", response.status_code)

        print("Risposta:")

        try:
            print(
                json.dumps(
                    response.json(),
                    indent=2,
                    ensure_ascii=False
                )
            )
        except Exception:
            print(response.text)

        print("=" * 70)
        print()

        response.raise_for_status()

    # ========================================================
    # PARSING RISPOSTA
    # ========================================================

    data = response.json()

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as e:

        print()
        print("ERRORE: risposta Gemini inattesa.")
        print(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            )
        )

        raise RuntimeError(
            f"Risposta Gemini non interpretabile: {e}"
        )

    text = text.strip()

    # Rimuove eventuali blocchi markdown JSON
    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    try:
        return json.loads(text)
    except json.JSONDecodeError:

        print()
        print("ERRORE: Gemini non ha restituito JSON valido.")
        print("Risposta ricevuta:")
        print(text)
        print()

        raise


# ============================================================
# ANALISI ARTICOLI
# ============================================================

analyzed = []
error_count = 0

for index, item in enumerate(items, start=1):

    title = clean_text(
        item.get("title")
        or item.get("name")
        or "Senza titolo",
        300
    )

    print(f"[{index}/{len(items)}] {title}")

    prompt = build_prompt(item)

    try:

        result = call_gemini(prompt)

        collector_score = safe_int(
            item.get("score")
            or item.get("collector_score")
            or item.get("source_score")
            or 0
        )

        ai_score = safe_int(
            result.get("ai_score"),
            0
        )

        reader_value = safe_int(
            result.get("reader_value"),
            0
        )

        italian_relevance = safe_int(
            result.get("italian_relevance"),
            0
        )

        originality = safe_int(
            result.get("originality"),
            0
        )

        urgency = safe_int(
            result.get("urgency"),
            0
        )

        commercial_value = safe_int(
            result.get("commercial_value"),
            0
        )

        publishable = bool(
            result.get("publishable", False)
        )

        suggested_category = normalize_category(
            result.get("suggested_category")
        )

        suggested_story_type = normalize_story_type(
            result.get("suggested_story_type")
        )

        # ====================================================
        # FINAL SCORE
        # ====================================================

        final_score = (
            collector_score * 0.35
            + ai_score * 0.25
            + reader_value * 0.15
            + italian_relevance * 0.10
            + originality * 0.05
            + commercial_value * 0.05
            + urgency * 0.05
        )

        # ====================================================
        # PICCOLE PENALITÀ EDITORIALI
        # ====================================================

        if suggested_story_type == "OFFERTA":
            if commercial_value < 50:
                final_score -= 8

        if suggested_story_type == "RUMOR":
            if ai_score < 75:
                final_score -= 8

        if suggested_story_type == "AZIENDALE":
            if reader_value < 70:
                final_score -= 10

        if suggested_category == "AI":
            if reader_value < 60:
                final_score -= 5

        final_score = max(
            0,
            min(100, round(final_score, 1))
        )

        # ====================================================
        # DECISIONE DI PUBBLICABILITÀ
        # ====================================================

        exclusion_reason = None

        if not publishable:
            exclusion_reason = "AI non approva"

        elif ai_score < MIN_AI_SCORE:
            exclusion_reason = (
                f"AI score troppo basso ({ai_score})"
            )

        elif collector_score < MIN_COLLECTOR_SCORE:
            exclusion_reason = (
                f"Collector score troppo basso ({collector_score})"
            )

        elif reader_value < MIN_READER_VALUE:
            exclusion_reason = (
                f"Reader value troppo basso ({reader_value})"
            )

        elif (
            suggested_story_type == "RUMOR"
            and ai_score < 75
        ):
            exclusion_reason = (
                f"Rumor sotto soglia ({ai_score})"
            )

        elif (
            suggested_story_type == "AZIENDALE"
            and reader_value < 75
        ):
            exclusion_reason = (
                f"Contenuto aziendale poco utile ({reader_value})"
            )

        elif (
            suggested_story_type == "OFFERTA"
            and commercial_value < 50
        ):
            exclusion_reason = (
                f"Offerta con valore commerciale basso "
                f"({commercial_value})"
            )

        # ====================================================
        # RISULTATO
        # ====================================================

        enriched = dict(item)

        enriched.update(
            {
                "ai_publishable": publishable,
                "ai_score": ai_score,
                "reader_value": reader_value,
                "italian_relevance": italian_relevance,
                "originality": originality,
                "urgency": urgency,
                "commercial_value": commercial_value,
                "final_score": final_score,
                "ai_reason": result.get("reason", ""),
                "ai_format": result.get(
                    "format",
                    "NEWS"
                ),
                "suggested_category": suggested_category,
                "suggested_story_type": suggested_story_type,
                "classification_issue": bool(
                    result.get(
                        "classification_issue",
                        False
                    )
                ),
                "exclusion_reason": exclusion_reason,
            }
        )

        analyzed.append(enriched)

        if exclusion_reason:

            print(
                f"   ESCLUSO: {exclusion_reason}"
            )

        else:

            print(
                f"   APPROVATO AI | "
                f"AI={ai_score} | "
                f"Reader={reader_value} | "
                f"Final={final_score} | "
                f"Categoria={suggested_category}"
            )

    except Exception as e:

        error_count += 1

        print(
            f"   ERRORE Gemini: "
            f"{type(e).__name__}: {e}"
        )

    time.sleep(REQUEST_DELAY)


# ============================================================
# SELEZIONE CANDIDATI
# ============================================================

approved = [
    item
    for item in analyzed
    if item.get("exclusion_reason") is None
]


# Ordina per final score
approved.sort(
    key=lambda x: x.get("final_score", 0),
    reverse=True
)


selected = []
category_counts = Counter()


# ============================================================
# PRIMO PASSAGGIO
# Garantisce almeno una categoria diversa quando possibile
# ============================================================

categories_seen = set()

for item in approved:

    category = item.get(
        "suggested_category",
        "Tecnologia"
    )

    if category in categories_seen:
        continue

    if category_counts[category] >= CATEGORY_LIMITS.get(
        category,
        4
    ):
        continue

    selected.append(item)

    category_counts[category] += 1
    categories_seen.add(category)

    if len(selected) >= MAX_FINAL_CANDIDATES:
        break


# ============================================================
# SECONDO PASSAGGIO
# Riempimento fino a 20
# ============================================================

if len(selected) < MAX_FINAL_CANDIDATES:

    selected_ids = {
        id(item)
        for item in selected
    }

    for item in approved:

        if id(item) in selected_ids:
            continue

        category = item.get(
            "suggested_category",
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

        if len(selected) >= MAX_FINAL_CANDIDATES:
            break


# ============================================================
# ORDINAMENTO FINALE
# ============================================================

selected.sort(
    key=lambda x: x.get("final_score", 0),
    reverse=True
)


# ============================================================
# ESCLUSIONI
# ============================================================

exclusion_counter = Counter()

for item in analyzed:

    reason = item.get("exclusion_reason")

    if reason:
        exclusion_counter[reason] += 1


if error_count:
    exclusion_counter[
        "Errore Gemini"
    ] += error_count


# ============================================================
# DISTRIBUZIONE
# ============================================================

distribution = Counter(
    item.get(
        "suggested_category",
        "Tecnologia"
    )
    for item in selected
)


# ============================================================
# OUTPUT
# ============================================================

output = {
    "filter_version": VERSION,
    "model": MODEL,

    "total_received": len(items),
    "total_analyzed": len(analyzed),

    "total_passed_ai": len(approved),

    "total_final_candidates": len(selected),

    "error_count": error_count,

    "exclusion_summary": dict(
        exclusion_counter
    ),

    "category_distribution": dict(
        distribution
    ),

    "items": selected,

    "all_analyzed": analyzed,
}


os.makedirs(
    os.path.dirname(OUTPUT_FILE),
    exist_ok=True
)


with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        output,
        f,
        ensure_ascii=False,
        indent=2
    )


# ============================================================
# RISULTATO
# ============================================================

print()
print("=" * 40)
print()
print("       RISULTATO AI VISION 2.6")
print()
print("=" * 40)
print()

print(
    "Articoli ricevuti:",
    len(items)
)

print(
    "Articoli analizzati:",
    len(analyzed)
)

print(
    "Approvati dall'AI:",
    len(approved)
)

print(
    "Candidati finali:",
    len(selected)
)

print()
print("ESCLUSIONI")
print("-" * 40)

if exclusion_counter:

    for reason, count in exclusion_counter.most_common():

        print(
            f"- {reason}: {count}"
        )

else:

    print("- Nessuna")


print()
print("DISTRIBUZIONE CATEGORIE")
print("-" * 40)

if distribution:

    for category, count in distribution.most_common():

        print(
            f"- {category}: {count}"
        )

else:

    print("- Nessuna categoria")


print()
print("CANDIDATI FINALI")
print("-" * 40)

for index, item in enumerate(
    selected,
    start=1
):

    title = clean_text(
        item.get("title")
        or item.get("name")
        or "Senza titolo",
        150
    )

    category = item.get(
        "suggested_category",
        "Tecnologia"
    )

    story_type = item.get(
        "suggested_story_type",
        "NEWS"
    )

    final_score = item.get(
        "final_score",
        0
    )

    print(
        f"{index}. [{category}] "
        f"[{story_type}] "
        f"[score {final_score}] "
        f"{title}"
    )


print()
print("=" * 40)
print()
print(
    "Output salvato in:",
    OUTPUT_FILE
)
print()
print("=" * 40)
