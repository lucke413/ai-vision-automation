#!/usr/bin/env python3

"""
AI Vision - RSS Collector

Raccoglie automaticamente articoli da feed RSS/Atom,
normalizza i dati, elimina duplicati e salva gli elementi
in data/rss_items.json.

Il file è pensato per essere eseguito da GitHub Actions.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import feedparser


# ============================================================
# CONFIGURAZIONE
# ============================================================

MAX_AGE_HOURS = 48
MAX_ITEMS_PER_FEED = 25
MAX_TOTAL_ITEMS = 150

REQUEST_TIMEOUT = 20

OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "rss_items.json"


# Feed iniziali.
#
# In questa fase preferiamo fonti tecnologiche/AI affidabili.
# Aggiungeremo successivamente altre fonti italiane e
# specializzate.
FEEDS = [
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "Tecnologia",
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "Tecnologia",
    },
    {
        "name": "Google AI",
        "url": "https://blog.google/technology/ai/rss/",
        "category": "AI",
    },
    {
        "name": "OpenAI",
        "url": "https://openai.com/news/rss.xml",
        "category": "AI",
    },
]


# ============================================================
# FUNZIONI UTILI
# ============================================================

def clean_text(text: str) -> str:
    """
    Rimuove HTML e spazi inutili.
    """
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_url(url: str) -> str:
    """
    Normalizza leggermente un URL per aiutare il
    riconoscimento dei duplicati.
    """
    if not url:
        return ""

    url = url.strip()

    # Rimuove alcuni parametri di tracking comuni.
    parsed = urlparse(url)

    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    if parsed.query:
        tracking_parameters = (
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "gclid",
            "fbclid",
        )

        query_parts = []

        for item in parsed.query.split("&"):
            if "=" not in item:
                continue

            key, value = item.split("=", 1)

            if key not in tracking_parameters:
                query_parts.append(f"{key}={value}")

        if query_parts:
            clean += "?" + "&".join(query_parts)

    return clean.rstrip("/")


def create_id(title: str, url: str) -> str:
    """
    Crea un ID stabile per riconoscere lo stesso articolo.
    """
    raw = f"{title.lower().strip()}|{normalize_url(url)}"

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:24]


def parse_date(entry: Any) -> datetime | None:
    """
    Cerca la data di pubblicazione/aggiornamento del feed.
    """
    parsed_time = None

    if getattr(entry, "published_parsed", None):
        parsed_time = entry.published_parsed

    elif getattr(entry, "updated_parsed", None):
        parsed_time = entry.updated_parsed

    if not parsed_time:
        return None

    try:
        return datetime.fromtimestamp(
            time.mktime(parsed_time),
            tz=timezone.utc,
        )
    except (ValueError, OverflowError, OSError):
        return None


def is_recent(date: datetime | None) -> bool:
    """
    Mantiene soltanto articoli entro MAX_AGE_HOURS.
    Se la fonte non fornisce una data, l'articolo viene
    mantenuto per non perdere contenuti potenzialmente validi.
    """
    if date is None:
        return True

    limit = datetime.now(timezone.utc) - timedelta(
        hours=MAX_AGE_HOURS
    )

    return date >= limit


def extract_image(entry: Any) -> str:
    """
    Cerca un'immagine disponibile nel feed.
    """
    # media_content
    media_content = getattr(entry, "media_content", None)

    if media_content:
        for media in media_content:
            if isinstance(media, dict):
                url = media.get("url")
                if url:
                    return url

    # media_thumbnail
    media_thumbnail = getattr(entry, "media_thumbnail", None)

    if media_thumbnail:
        for media in media_thumbnail:
            if isinstance(media, dict):
                url = media.get("url")
                if url:
                    return url

    # enclosure
    enclosures = getattr(entry, "enclosures", None)

    if enclosures:
        for enclosure in enclosures:
            if isinstance(enclosure, dict):
                mime_type = enclosure.get("type", "")

                if mime_type.startswith("image/"):
                    url = enclosure.get("href") or enclosure.get("url")

                    if url:
                        return url

    return ""


def get_entry_description(entry: Any) -> str:
    """
    Recupera una descrizione disponibile.
    """
    summary = getattr(entry, "summary", "")

    if not summary:
        summary = getattr(entry, "description", "")

    return clean_text(summary)


# ============================================================
# RACCOLTA
# ============================================================

def collect_feed(feed_config: dict[str, str]) -> list[dict[str, Any]]:
    """
    Legge un singolo feed RSS/Atom.
    """
    source_name = feed_config["name"]
    feed_url = feed_config["url"]
    category = feed_config["category"]

    print(f"\n[RSS] {source_name}")
    print(f"      {feed_url}")

    try:
        feed = feedparser.parse(feed_url)
    except Exception as exc:
        print(f"      ERRORE: {exc}")
        return []

    if getattr(feed, "bozo", False):
        print("      ATTENZIONE: il feed potrebbe contenere dati non standard.")

    entries = getattr(feed, "entries", [])

    if not entries:
        print("      Nessun articolo trovato.")
        return []

    results = []

    for entry in entries[:MAX_ITEMS_PER_FEED]:

        title = clean_text(
            getattr(entry, "title", "")
        )

        url = normalize_url(
            getattr(entry, "link", "")
        )

        if not title or not url:
            continue

        published_at = parse_date(entry)

        if not is_recent(published_at):
            continue

        description = get_entry_description(entry)

        image_url = extract_image(entry)

        author = ""

        if getattr(entry, "author", None):
            author = clean_text(entry.author)

        item = {
            "id": create_id(title, url),
            "source": source_name,
            "source_feed": feed_url,
            "category_hint": category,
            "title": title,
            "url": url,
            "description": description,
            "image_url": image_url,
            "author": author,
            "published_at": (
                published_at.isoformat()
                if published_at
                else None
            ),
            "collected_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        results.append(item)

    print(f"      Articoli validi: {len(results)}")

    return results


# ============================================================
# DEDUPLICAZIONE
# ============================================================

def deduplicate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Elimina duplicati usando ID e URL.
    """
    seen_ids = set()
    seen_urls = set()

    unique = []

    for item in items:

        item_id = item["id"]
        url = normalize_url(item["url"])

        if item_id in seen_ids:
            continue

        if url in seen_urls:
            continue

        seen_ids.add(item_id)
        seen_urls.add(url)

        unique.append(item)

    return unique


# ============================================================
# ORDINAMENTO
# ============================================================

def sort_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Mette prima gli articoli più recenti.
    """
    return sorted(
        items,
        key=lambda item: item.get("published_at") or "",
        reverse=True,
    )


# ============================================================
# SALVATAGGIO
# ============================================================

def save_items(items: list[dict[str, Any]]) -> None:
    """
    Salva gli articoli in JSON.
    """
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "max_age_hours": MAX_AGE_HOURS,

        "total_items": len(items),

        "items": items,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    print("")
    print("=" * 60)
    print("          AI VISION - RSS COLLECTOR")
    print("=" * 60)
    print("")

    all_items = []

    for feed_config in FEEDS:

        try:
            items = collect_feed(feed_config)

            all_items.extend(items)

        except Exception as exc:

            print(
                f"[ERRORE] {feed_config['name']}: {exc}",
                file=sys.stderr,
            )

    print("")
    print("-" * 60)

    print(
        f"Articoli raccolti prima della deduplicazione: "
        f"{len(all_items)}"
    )

    all_items = deduplicate(all_items)

    print(
        f"Articoli dopo deduplicazione: "
        f"{len(all_items)}"
    )

    all_items = sort_items(all_items)

    all_items = all_items[:MAX_TOTAL_ITEMS]

    print(
        f"Articoli salvati: "
        f"{len(all_items)}"
    )

    save_items(all_items)

    print("")
    print(f"File creato: {OUTPUT_FILE}")
    print("")
    print("=" * 60)
    print("              RACCOLTA COMPLETATA")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
