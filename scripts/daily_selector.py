#!/usr/bin/env python3
"""Seleziona i cinque articoli da preparare per la pubblicazione giornaliera.

Il modulo non pubblica nulla e non chiama servizi esterni. Usa esclusivamente
il risultato approvato dal filtro Gemini.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "ai_candidates.json"
OUTPUT_FILE = BASE_DIR / "data" / "daily_articles.json"

VERSION = "1.1"
DAILY_LIMIT = 5
MAX_OFFERS = 1
MAX_PER_CATEGORY = 1
MAX_PER_SOURCE = 2


def canonical_url(value: object) -> str:
    """Normalizza l'URL e rimuove i parametri di tracciamento."""
    try:
        parts = urlsplit(str(value or "").strip())
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return ""
        query = [
            (key, val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
            and key.lower() not in {"fbclid", "gclid"}
        ]
        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                parts.path,
                urlencode(query),
                "",
            )
        )
    except ValueError:
        return ""


def stable_id(item: dict) -> str:
    """Restituisce un identificativo persistente per deduplica futura."""
    existing = str(item.get("cluster_id") or "").strip()
    if existing:
        return existing
    value = canonical_url(item.get("url")) or str(item.get("title") or "").strip().lower()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def score_key(item: dict) -> tuple[float, float, str]:
    return (
        float(item.get("final_score") or 0),
        float(item.get("ai_analysis", {}).get("ai_score") or 0),
        str(item.get("title") or ""),
    )


def valid_candidates(data: dict) -> list[dict]:
    status = data.get("status")
    if status not in {"ok", "ok_with_warnings"}:
        raise RuntimeError("Il risultato AI non è utilizzabile.")
    if status == "ok" and data.get("total_unprocessed", 0) != 0:
        raise RuntimeError("Il risultato AI contiene articoli non elaborati.")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise RuntimeError("Nessun candidato AI disponibile.")

    result = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = canonical_url(item.get("url"))
        if not title or not url:
            continue
        identifier = stable_id(item)
        if identifier in seen:
            continue
        seen.add(identifier)
        copy = dict(item)
        copy["article_id"] = identifier
        copy["url"] = url
        result.append(copy)
    return sorted(result, key=score_key, reverse=True)


def select_daily(items: list[dict]) -> list[dict]:
    """Seleziona una rosa varia, con al massimo un'offerta."""
    selected: list[dict] = []
    categories = Counter()
    sources = Counter()
    offers = 0

    # Prima passata: una categoria diversa per ogni slot quando possibile.
    for distinct_categories in (True, False):
        for item in items:
            if len(selected) >= DAILY_LIMIT:
                return sorted(selected, key=score_key, reverse=True)
            category = str(item.get("category") or "Tecnologia")
            source = str(item.get("source") or "")
            is_offer = category == "Offerte & Prezzi" or item.get("story_type") == "OFFERTA"
            if item["article_id"] in {x["article_id"] for x in selected}:
                continue
            if sources[source] >= MAX_PER_SOURCE:
                continue
            if categories[category] >= MAX_PER_CATEGORY:
                continue
            if distinct_categories and categories[category] > 0:
                continue
            if is_offer and offers >= MAX_OFFERS:
                continue
            selected.append(item)
            categories[category] += 1
            sources[source] += 1
            offers += int(is_offer)

    return sorted(selected, key=score_key, reverse=True)


def main() -> int:
    if not INPUT_FILE.is_file():
        raise FileNotFoundError(f"File non trovato: {INPUT_FILE}")
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    candidates = valid_candidates(data)
    selected = select_daily(candidates)
    if len(selected) != DAILY_LIMIT:
        raise RuntimeError(f"Solo {len(selected)} articoli selezionabili su {DAILY_LIMIT}.")

    output = {
        "selector_version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "source_filter_version": data.get("filter_version"),
        "daily_limit": DAILY_LIMIT,
        "total_candidates": len(candidates),
        "selected_count": len(selected),
        "category_distribution": dict(Counter(x.get("category", "Tecnologia") for x in selected)),
        "offer_count": sum(
            1
            for x in selected
            if x.get("category") == "Offerte & Prezzi" or x.get("story_type") == "OFFERTA"
        ),
        "items": selected,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temporary, OUTPUT_FILE)

    print("AI VISION - DAILY SELECTOR")
    print(f"Candidati disponibili: {len(candidates)}")
    print(f"Articoli selezionati: {len(selected)}")
    print(f"Offerte selezionate: {output['offer_count']}")
    for index, item in enumerate(selected, 1):
        print(f"{index}. [{item.get('final_score', 0)}] [{item.get('category', 'Tecnologia')}] {item['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
