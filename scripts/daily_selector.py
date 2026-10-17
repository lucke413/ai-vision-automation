#!/usr/bin/env python3
"""Prepara gli articoli del giorno e una piccola coda di riserva.

Il selettore non pubblica nulla e non chiama servizi esterni. Se sono
disponibili meno di tre candidati, usa comunque quelli disponibili e
scrive un avviso: il workflow non deve fermarsi per una carenza temporanea.
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

VERSION = "2.6"
DAILY_LIMIT = 3
RESERVE_LIMIT = 3
MAX_OFFERS = 1
MAX_GUIDES_PER_DAY = 1
MAX_TUTORIALS_PER_DAY = 1
MAX_PRACTICAL_PER_DAY = 1
# Modalità qualità AdSense: massimo tre uscite al giorno, con al massimo una guida/tutorial.
# Espansione graduale: al massimo un articolo di categoria nuova, mai obbligatorio.
EXPANSION_CATEGORIES = {"Casa smart", "Accessori e postazioni"}
MAX_EXPANSION_ARTICLES = 1


def expansion_room(selected: list[dict], candidate: dict) -> bool:
    return (candidate.get("category") not in EXPANSION_CATEGORIES or
            sum(item.get("category") in EXPANSION_CATEGORIES for item in selected)
            < MAX_EXPANSION_ARTICLES)



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
            (parts.scheme.lower(), parts.netloc.lower(), parts.path,
             urlencode(query), "")
        )
    except ValueError:
        return ""


def stable_id(item: dict) -> str:
    existing = str(item.get("cluster_id") or "").strip()
    if existing:
        return existing
    value = canonical_url(item.get("url")) or str(item.get("title") or "").strip().lower()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def score_key(item: dict) -> tuple[float, float, str]:
    analysis = item.get("ai_analysis") or {}
    return (
        float(item.get("final_score") or 0),
        float(analysis.get("ai_score") or 0),
        str(item.get("title") or ""),
    )


def valid_candidates(data: dict) -> list[dict]:
    """Restituisce i candidati utilizzabili, anche con output parziale."""
    status = data.get("status")
    if status not in {"ok", "ok_with_warnings", "empty"}:
        raise RuntimeError("Il risultato AI non è utilizzabile.")

    items = data.get("items")
    if not isinstance(items, list):
        return []

    result: list[dict] = []
    seen: set[str] = set()
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


def editorial_room(selected: list[dict], candidate: dict) -> bool:
    """Limita guide e tutorial a un solo contenuto pratico al giorno."""
    kind = candidate.get("editorial_kind")
    limits = {"GUIDA": MAX_GUIDES_PER_DAY, "TUTORIAL": MAX_TUTORIALS_PER_DAY}
    if kind not in limits:
        return True
    if sum(x.get("editorial_kind") in {"GUIDA", "TUTORIAL"} for x in selected) >= MAX_PRACTICAL_PER_DAY:
        return False
    return sum(x.get("editorial_kind") == kind for x in selected) < limits[kind]


def is_offer(item: dict) -> bool:
    return (
        item.get("category") == "Offerte & Prezzi"
        or item.get("story_type") == "OFFERTA"
    )


def select_daily(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Modalità qualità: fino a tre articoli, con al massimo un contenuto pratico.

    Guide e tutorial non sono obbligatori: gli slot restano disponibili per
    notizie con i gate editoriali invariati e non si forza mai il volume.
    """
    if not items:
        return [], []

    selected: list[dict] = []
    selected_ids: set[str] = set()
    categories: set[str] = set()
    offers = 0

    def offer_ok(item: dict) -> bool:
        return not is_offer(item) or offers < MAX_OFFERS

    def add(item: dict) -> bool:
        nonlocal offers
        identifier = item["article_id"]
        if identifier in selected_ids or not offer_ok(item):
            return False
        if not expansion_room(selected, item) or not editorial_room(selected, item):
            return False
        if len(selected) >= DAILY_LIMIT:
            return False
        selected.append({**item, "publication_slot": "today"})
        selected_ids.add(identifier)
        categories.add(str(item.get("category") or "Tecnologia"))
        offers += int(is_offer(item))
        return True

    practical = [x for x in items if x.get("editorial_kind") in {"GUIDA", "TUTORIAL"}]
    news = [x for x in items if x.get("editorial_kind") not in {"GUIDA", "TUTORIAL"}]

    # Una sola rubrica pratica per giornata: scegli la migliore già ordinata
    # per punteggio ed evita raffiche di guide/template nello stesso giorno.
    for item in practical:
        if add(item):
            break

    # La cronaca tecnologica resta centrale; prima privilegiamo categorie diverse.
    for item in news:
        if len(selected) >= DAILY_LIMIT:
            break
        if str(item.get("category") or "Tecnologia") not in categories:
            add(item)
    for item in news:
        if len(selected) >= DAILY_LIMIT:
            break
        add(item)

    # Never replace failed news with an extra tutorial or guide.
    # Reserve candidates come from RSS only, and retain their quality gates.
    reserves: list[dict] = []
    for item in news:
        if len(reserves) >= RESERVE_LIMIT:
            break
        if item["article_id"] in selected_ids:
            continue
        if any(item["article_id"] == reserve["article_id"] for reserve in reserves):
            continue
        reserves.append({**item, "publication_slot": "reserve"})

    return selected, reserves


def main() -> int:
    if not INPUT_FILE.is_file():
        raise FileNotFoundError(f"File non trovato: {INPUT_FILE}")
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    candidates = valid_candidates(data)
    selected, reserves = select_daily(candidates)
    status = "ok" if len(selected) == DAILY_LIMIT else ("ok_with_warnings" if selected else "empty")
    warnings = []
    if len(selected) < DAILY_LIMIT:
        warnings.append(f"Solo {len(selected)} articoli disponibili su {DAILY_LIMIT}; il run prosegue.")
    if not candidates:
        warnings.append("Nessun candidato valido disponibile in questo run.")

    output = {
        "selector_version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "warnings": warnings,
        "source_filter_version": data.get("filter_version"),
        "daily_limit": DAILY_LIMIT,
        "reserve_limit": RESERVE_LIMIT,
        "total_candidates": len(candidates),
        "selected_count": len(selected),
        "reserve_count": len(reserves),
        "category_distribution": dict(Counter(x.get("category", "Tecnologia") for x in selected)),
        "offer_count": sum(1 for x in selected if is_offer(x)),
        "items": selected,
        "reserve_items": reserves,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temporary, OUTPUT_FILE)

    print("AI VISION - DAILY SELECTOR")
    print(f"Candidati disponibili: {len(candidates)}")
    print(f"Articoli selezionati: {len(selected)}/{DAILY_LIMIT}")
    print(f"Articoli di scorta: {len(reserves)}/{RESERVE_LIMIT}")
    print(f"Offerte selezionate: {output['offer_count']}")
    for index, item in enumerate(selected, 1):
        print(f"{index}. [{item.get('final_score', 0)}] [{item.get('category', 'Tecnologia')}] {item['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
