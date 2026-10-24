#!/usr/bin/env python3
"""Inserisce link affiliati SOLO da IconA Altervista, mai tag Amazon personali.

Non genera link affiliati, non interroga API private e non modifica URL.
Servono link gia' emessi dalla bacheca IconA, associati a prodotti precisi
e attestati dal gestore. Senza una configurazione esplicita non inserisce nulla.
"""
from __future__ import annotations

import html
import json
import os
import re
import unicodedata
from urllib.parse import urlsplit

MAX_ENTRIES = 100
MAX_LINKS_PER_ARTICLE = 2
PRODUCT_CATEGORIES = {
    "Offerte & Prezzi", "Gaming", "PC & Hardware", "Smartphone & Mobile",
    "Casa smart", "Accessori e postazioni", "Gadget & Consumer Tech",
    "Tecnologia",
}


def _enabled() -> bool:
    return os.environ.get("ICONA_ENABLED", "").strip().lower() in {"true", "1", "yes", "on"}


def _valid_url(url: str) -> bool:
    if not url or len(url) > 1500 or any(ch.isspace() or ord(ch) < 32 for ch in url):
        return False
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme == "https"
            and host in {"amazon.it", "www.amazon.it", "amzn.to"}
            and parsed.username is None and parsed.password is None
            and parsed.port in (None, 443)
            and not parsed.fragment
        )
    except ValueError:
        return False


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _matches_product(title: str, product: str) -> bool:
    if len(product) < 10 or len(product.split()) < 2:
        return False
    expression = r"(?<!\w)" + r"\s+".join(re.escape(word) for word in _normalize(product).split()) + r"(?!\w)"
    return re.search(expression, _normalize(title)) is not None


def load_catalog() -> list[dict]:
    """Solo JSON di link approvati in bacheca; nessun link senza conferma IconA."""
    if not _enabled():
        return []
    raw = os.environ.get("ICONA_LINKS_JSON", "").strip()
    if not raw:
        print("    ICONA: attivazione richiesta ma nessun catalogo; link disabilitati.")
        return []
    try:
        values = json.loads(raw)
    except (ValueError, TypeError):
        print("    ICONA: catalogo non valido; link disabilitati.")
        return []
    if not isinstance(values, list) or len(values) > MAX_ENTRIES:
        print("    ICONA: catalogo deve essere un elenco limitato di prodotti.")
        return []
    entries: list[dict] = []
    seen: set[str] = set()
    for entry in values:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("product_name") or "").strip()
        url = str(entry.get("url") or "").strip()
        key = _normalize(name)
        if (entry.get("source") != "altervista_icona" or entry.get("confirmed") is not True
                or not _valid_url(url) or not _matches_product(name, name)
                or key in seen):
            continue
        seen.add(key)
        entries.append({"product_name": name, "url": url})
    return entries


def affiliate_html(draft: dict, catalog: list[dict] | None = None) -> tuple[str, int]:
    """Aggiunge al massimo due link; un prodotto deve comparire nel titolo."""
    if draft.get("editorial_kind") in {"GUIDA", "TUTORIAL"}:
        return "", 0
    if (draft.get("category") not in PRODUCT_CATEGORIES
            and draft.get("story_type") != "OFFERTA"):
        return "", 0
    if catalog is None:
        catalog = load_catalog()
    title = str(draft.get("title") or "")
    matches = [entry for entry in catalog if _matches_product(title, entry["product_name"])]
    if not matches:
        return "", 0
    # Evita di associare un modello piu' generico a quello specifico.
    # Due prodotti diversi sono consentiti solo se entrambi nominati nel titolo.
    matches.sort(key=lambda x: len(x["product_name"]), reverse=True)
    selected = matches[:MAX_LINKS_PER_ARTICLE]
    parts = []
    for entry in selected:
        url = html.escape(entry["url"], quote=True)
        name = html.escape(entry["product_name"])
        parts.append(
            '<li><a href="' + url + '" rel="sponsored nofollow noopener noreferrer" '
            'target="_blank">Verifica prezzo e disponibilità di ' + name +
            ' su Amazon</a></li>'
        )
    block = (
        '<aside class="av-icona-affiliation" aria-label="Collegamenti commerciali">'
        '<p><strong>Link di affiliazione IconA</strong> — '
        'questo articolo contiene collegamenti commerciali; '
        'potremmo ricevere una commissione sugli acquisti idonei.</p>'
        '<ul>' + "".join(parts) + '</ul>'
        '<p>Prezzi e disponibilità possono variare: controllali direttamente su Amazon.</p>'
        '</aside>'
    )
    return block, len(selected)
