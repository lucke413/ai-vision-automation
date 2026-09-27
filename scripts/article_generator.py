#!/usr/bin/env python3
"""Genera bozze editoriali originali dai cinque articoli giornalieri.

Il modulo non pubblica su WordPress e non inserisce ancora link affiliati.
Produce soltanto data/article_drafts.json per la revisione.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "daily_articles.json"
OUTPUT_FILE = BASE_DIR / "data" / "article_drafts.json"

VERSION = "1.0"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
MAX_ITEMS = 5
MAX_RETRIES = 4
REQUEST_DELAY = 6.0
RETRY_BUFFER = 2.0
REQUEST_TIMEOUT = 90

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

VALID_TYPES = {
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

SYSTEM_PROMPT = """
Sei il redattore di AI Vision, magazine italiano di tecnologia.
Scrivi una BOZZA ORIGINALE in italiano basata soltanto sui dati della fonte
forniti nel prompt.

REGOLE EDITORIALI:
- non copiare frasi dalla fonte;
- non inventare numeri, date, prezzi, caratteristiche o dichiarazioni;
- distingui i fatti riportati dalla fonte dalle interpretazioni;
- se un dato non è disponibile, non aggiungerlo;
- usa uno stile chiaro per un lettore italiano generalista;
- non chiamare "recensione" un contenuto che non contiene elementi di prova;
- per un'offerta, indica che prezzo e disponibilità devono essere verificati
  prima della pubblicazione;
- non inserire link affiliati, codici tracking o pubblicità nel testo;
- non presentare la bozza come verifica indipendente dei fatti.

Il risultato verrà revisionato prima della pubblicazione.
Restituisci esclusivamente JSON valido.
"""


class GeneratorFatalError(RuntimeError):
    """Errore che rende impossibile completare il lotto di bozze."""


def extract_json(text: str) -> dict | None:
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(cleaned[start : end + 1])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None


def parse_retry_delay(response: requests.Response) -> float | None:
    try:
        payload = response.json()
        details = payload.get("error", {}).get("details", []) or []
        for detail in details:
            if isinstance(detail, dict) and detail.get("retryDelay"):
                match = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(detail["retryDelay"]))
                if match:
                    return float(match.group(1))
    except (ValueError, TypeError, AttributeError):
        pass
    match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", response.text, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def call_gemini(prompt: str, api_key: str) -> dict:
    if not api_key:
        raise GeneratorFatalError("GEMINI_API_KEY non presente.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.35,
            "responseMimeType": "application/json",
        },
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    for attempt in range(1, MAX_RETRIES + 1):
        wait_time = min(60.0, (2**attempt) + random.uniform(0.5, 1.5))
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates") or []
                parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
                result = extract_json(text)
                if result is None:
                    raise GeneratorFatalError("Gemini ha restituito JSON non valido.")
                return result
            if response.status_code in (400, 401, 403, 404):
                raise GeneratorFatalError(f"Gemini HTTP {response.status_code}: richiesta non autorizzata o non valida.")
            if response.status_code == 429:
                delay = parse_retry_delay(response)
                if delay is None:
                    delay = 30.0
                if not math.isfinite(delay) or delay > 120 or attempt == MAX_RETRIES:
                    raise GeneratorFatalError("Limite Gemini persistente (429).")
                wait_time = max(0.0, delay) + RETRY_BUFFER
            elif not 500 <= response.status_code < 600:
                raise GeneratorFatalError(f"Gemini HTTP {response.status_code}.")
            print(f"    Gemini HTTP {response.status_code}, tentativo {attempt}/{MAX_RETRIES}.")
        except GeneratorFatalError:
            raise
        except requests.exceptions.RequestException:
            print(f"    Errore di rete Gemini, tentativo {attempt}/{MAX_RETRIES}.")
        except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
            raise GeneratorFatalError(f"Risposta Gemini non interpretabile: {type(exc).__name__}.") from exc
        if attempt < MAX_RETRIES:
            time.sleep(wait_time)
    raise GeneratorFatalError("Gemini non ha completato la generazione.")


def build_prompt(item: dict) -> str:
    title = str(item.get("title") or "")[:500]
    description = str(item.get("description") or "")[:5000]
    return f"""
Genera una bozza per questo candidato editoriale.

ID ARTICOLO: {item.get('article_id', '')}
TITOLO DELLA FONTE: {title}
DESCRIZIONE DELLA FONTE: {description}
FONTE: {item.get('source', '')}
URL ORIGINALE: {item.get('url', '')}
CATEGORIA: {item.get('category', 'Tecnologia')}
TIPO: {item.get('story_type', 'NEWS')}
PUNTEGGIO EDITORIALE: {item.get('final_score', 0)}

Restituisci esattamente questo schema:
{{
  "title": "titolo originale in italiano",
  "excerpt": "riassunto di massimo duecento caratteri",
  "body_markdown": "articolo originale di 450-700 parole in Markdown",
  "seo_title": "titolo SEO di massimo 60 caratteri",
  "seo_description": "descrizione SEO di massimo 155 caratteri",
  "slug": "slug-in-minuscolo-con-trattini",
  "tags": ["tag1", "tag2", "tag3"],
  "fact_check_notes": ["dati da verificare prima della pubblicazione"],
  "affiliate_candidate": false,
  "needs_review": true
}}

Per un'offerta imposta affiliate_candidate a true e inserisci nelle
fact_check_notes la verifica di prezzo, disponibilità e condizioni.
    """


def normalize_draft(raw: dict, item: dict) -> dict:
    required = {"title", "excerpt", "body_markdown", "seo_title", "seo_description", "slug", "tags", "fact_check_notes"}
    if not required.issubset(raw):
        raise GeneratorFatalError("Bozza Gemini priva di campi obbligatori.")
    title = str(raw["title"]).strip()
    body = str(raw["body_markdown"]).strip()
    if len(title) < 10 or len(body) < 300:
        raise GeneratorFatalError("Bozza troppo breve o senza titolo valido.")
    category = item.get("category", "Tecnologia")
    story_type = item.get("story_type", "NEWS")
    if category not in VALID_CATEGORIES:
        category = "Tecnologia"
    if story_type not in VALID_TYPES:
        story_type = "NEWS"
    tags = raw["tags"] if isinstance(raw["tags"], list) else []
    notes = raw["fact_check_notes"] if isinstance(raw["fact_check_notes"], list) else []
    offer = category == "Offerte & Prezzi" or story_type == "OFFERTA"
    source_id = str(item.get("article_id") or "")
    draft_id = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:20]
    return {
        "draft_id": draft_id,
        "article_id": source_id,
        "status": "draft",
        "needs_review": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_url": item.get("url"),
        "source": item.get("source"),
        "category": category,
        "story_type": story_type,
        "title": title,
        "excerpt": str(raw["excerpt"]).strip()[:300],
        "body_markdown": body,
        "seo_title": str(raw["seo_title"]).strip()[:70],
        "seo_description": str(raw["seo_description"]).strip()[:170],
        "slug": re.sub(r"[^a-z0-9-]", "", str(raw["slug"]).lower().replace(" ", "-")).strip("-"),
        "tags": [str(tag).strip() for tag in tags[:8] if str(tag).strip()],
        "fact_check_notes": [str(note).strip() for note in notes[:10] if str(note).strip()],
        "affiliate_candidate": bool(raw.get("affiliate_candidate", offer)) if offer else False,
    }


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not INPUT_FILE.is_file():
        raise FileNotFoundError(f"File non trovato: {INPUT_FILE}")
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    items = data.get("items")
    if not isinstance(items, list) or len(items) != MAX_ITEMS:
        raise RuntimeError(f"La selezione deve contenere esattamente {MAX_ITEMS} articoli.")

    drafts = []
    fatal_error = None
    for index, item in enumerate(items, 1):
        print(f"[{index}/{len(items)}] {item.get('title', '')}")
        try:
            drafts.append(normalize_draft(call_gemini(build_prompt(item), api_key), item))
        except GeneratorFatalError as exc:
            fatal_error = str(exc)
            print(f"    ERRORE: {fatal_error}")
            break
        if index < len(items):
            time.sleep(REQUEST_DELAY)

    output = {
        "generator_version": VERSION,
        "model": MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if len(drafts) == MAX_ITEMS else "error",
        "error": fatal_error,
        "total_requested": len(items),
        "total_generated": len(drafts),
        "items": drafts,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temporary, OUTPUT_FILE)
    print(f"Bozze generate: {len(drafts)}/{MAX_ITEMS}")
    print(f"Output: {OUTPUT_FILE}")
    return 0 if output["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
