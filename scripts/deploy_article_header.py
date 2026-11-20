"""Publish only the AI Vision article header snippet and verify live HTML."""
import os
from pathlib import Path
from time import time
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

SITE = "https://aivision.altervista.org"
PLUGIN = "code-snippets/code-snippets"
SNIPPETS = "/code-snippets/v1/snippets"
NAME = "AI Vision: Top Tags e notizie negli articoli"
MARKER = "function aivision_article_header_strips()"
SOURCE = Path(__file__).resolve().parents[1] / "wordpress/article-header.php"
ARTICLES = (
    "/migliori-sedie-gaming-modelli-fasce-prezzo/",
    "/amazon-black-friday-2026-11-19-2/",
)
ARCHIVE = "/category/offerte-2/"
SELECTORS = (".mg-tpt-tag-area", ".mg-latest-news-sec")


def wp(session, method, route, **kwargs):
    response = session.request(method, SITE + "/wp-json" + route, timeout=(10, 60),
                               allow_redirects=False, **kwargs)
    if not response.ok or response.is_redirect:
        try:
            error = response.json().get("code", "")
        except ValueError:
            error = ""
        raise RuntimeError(f"{method} {route}: HTTP {response.status_code} {error}")
    return response.json()


def get_page(session, path):
    response = session.get(SITE + path, params={"aivision_header_check": int(time())},
                           timeout=(10, 25), allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError(f"Pagina pubblica {path}: HTTP {response.status_code}")
    return BeautifulSoup(response.content, "html.parser")


def strips(page):
    return [page.select(selector) for selector in SELECTORS]


def destinations(element):
    return [urlsplit(a["href"]).path for a in element.select("a[href]")]


def verify(session):
    home = strips(get_page(session, "/"))
    if any(len(items) != 1 for items in home):
        raise RuntimeError("La home non contiene entrambe le barre singole di Newsup.")
    expected_tags, expected_news = (destinations(items[0]) for items in home)
    for path in ARTICLES:
        page = get_page(session, path)
        sections = strips(page)
        if any(len(items) != 1 for items in sections):
            raise RuntimeError(f"Barre mancanti o duplicate su {path}")
        tags, ticker = (items[0] for items in sections)
        if not page.select_one("main.single-class") or any(element.find_parent("main") for element in (tags, ticker)):
            raise RuntimeError(f"Posizione delle barre inattesa su {path}")
        if destinations(tags) != expected_tags or not set(destinations(ticker)).intersection(expected_news):
            raise RuntimeError(f"Tag o notizie incoerenti con la home su {path}")
        if not ticker.select_one(".marquee") or not page.select_one("#newsup-marquee-js-js"):
            raise RuntimeError(f"Script o elemento Newsup del testo scorrevole mancante su {path}")
        print(f"Verificati {len(destinations(tags))} tag e {len(destinations(ticker))} notizie su {path}")
    if any(strips(get_page(session, ARCHIVE))):
        raise RuntimeError("Le barre compaiono nell'archivio delle offerte.")
    print("Verificate la home e la pagina archivio.")


def ensure_snippets_plugin(session):
    plugins = wp(session, "GET", "/wp/v2/plugins", params={"context": "edit", "_fields": "plugin,status"})
    installed = next((item for item in plugins if item["plugin"] == PLUGIN), None)
    if installed:
        if installed["status"] != "active":
            raise RuntimeError("Code Snippets è già presente ma inattivo.")
        return
    installed = wp(session, "POST", "/wp/v2/plugins", json={"slug": "code-snippets", "status": "active"})
    if installed.get("plugin") != PLUGIN or installed.get("status") != "active":
        raise RuntimeError("WordPress non ha confermato l'attivazione di Code Snippets.")
    print("Code Snippets installato e attivo.")


def deploy(admin, public):
    ensure_snippets_plugin(admin)
    code = SOURCE.read_text(encoding="utf-8").removeprefix("<?php\n")
    matches = [item for item in wp(admin, "GET", SNIPPETS) if item.get("name") == NAME]
    if len(matches) > 1 or any(item.get("code", "").strip() != code.strip() for item in matches):
        raise RuntimeError("Uno snippet con questo nome ha contenuto diverso dal repository.")
    if matches and matches[0]["active"]:
        verify(public)
        return
    if matches:
        saved = matches[0]
    else:
        saved = wp(admin, "POST", SNIPPETS, json={"name": NAME, "code": code, "scope": "front-end", "active": False})
    if MARKER not in saved.get("code", "") or saved.get("code_error"):
        raise RuntimeError("Il contenuto dello snippet non è stato salvato correttamente.")
    route = f"{SNIPPETS}/{int(saved['id'])}"
    try:
        result = wp(admin, "POST", route + "/activate")
        if not result.get("active"):
            raise RuntimeError("WordPress non ha confermato l'attivazione dello snippet.")
        verify(public)
    except (RuntimeError, requests.RequestException):
        wp(admin, "POST", route + "/deactivate")
        print("Snippet disattivato dopo verifica pubblica fallita.")
        raise


def main():
    base = os.environ.get("WP_BASE_URL", "").rstrip("/").removesuffix("/wp-json")
    user, password = (os.environ.get(key, "") for key in ("WP_USERNAME", "WP_APP_PASSWORD"))
    if base != SITE or not user or not password:
        raise SystemExit("Configurazione WordPress AI Vision mancante.")
    with requests.Session() as admin, requests.Session() as public:
        admin.auth = (user, password)
        deploy(admin, public)


if __name__ == "__main__":
    main()
