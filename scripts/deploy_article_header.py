"""Publish AI Vision article layout snippets and verify live HTML."""
import argparse
import os
from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from time import time
from urllib.parse import parse_qs, unquote, urlsplit

import requests
from bs4 import BeautifulSoup

SITE = "https://aivision.altervista.org"
PLUGIN = "code-snippets/code-snippets"
SNIPPETS = "/code-snippets/v1/snippets"
NAME = "AI Vision: Top Tags e notizie negli articoli"
SOURCE = Path(__file__).resolve().parents[1] / "wordpress/article-header.php"
RELATED_NAME = "AI Vision: copertine e titoli degli articoli correlati"
RELATED_SOURCE = SOURCE.with_name("related-cards.php")
READING_NAME = "AI Vision: articoli di tendenza e più letti"
READING_SOURCE = SOURCE.with_name("reading-widget.php")
PREVIOUS_READING_HASH = "28e535440a8a1a6174432563d67ca53394f08d7f6a227d6a36769b0acea321bb"
NAVIGATION_NAME = "AI Vision: navigazione offerte e indice articoli"
NAVIGATION_SOURCE = SOURCE.with_name("editorial-navigation.php")
ARTICLES = (
    "/migliori-sedie-gaming-modelli-fasce-prezzo/",
    "/amazon-black-friday-2026-11-19-2/",
)
ARCHIVE = "/category/offerte-2/"
CATEGORIES = (ARCHIVE, "/category/guide/", "/category/ai-pratica/")
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


def verify_related_cards(session):
    style_id = "#aivision-related-cards-inline-css"
    paths = ("/amazon-offerte-ordinarie-2026-11-19/", ARTICLES[0])
    for path in paths:
        page = get_page(session, path)
        style = page.select_one(style_id)
        cards = page.select(".single-class .mg-featured-slider > .row > .col-md-4 > .mg-blog-post-3")
        if not style or not cards or any(not card.select_one("h4.title a[href]") for card in cards):
            raise RuntimeError(f"Stile o schede correlate mancanti su {path}")
        print(f"Verificato lo stile per {len(cards)} schede correlate su {path}")
    if any(get_page(session, path).select_one(style_id) for path in ("/", ARCHIVE)):
        raise RuntimeError("Lo stile per gli articoli correlati compare fuori dagli articoli.")


def verify_reading_widget(session):
    for path in ("/", *ARTICLES, *CATEGORIES):
        page = get_page(session, path)
        widget = page.select(".aiv-reading")
        container = ".top-right-area .aiv-reading" if path == "/" else "#sidebar-right .aiv-reading"
        if not page.select_one("#aivision-reading-widget-inline-css"):
            raise RuntimeError(f"Stile del menu lingua mancante su {path}")
        if path in CATEGORIES:
            language = page.select_one("#sidebar-right .aiv-language")
        elif len(widget) == 1 and page.select_one(container) and len(widget[0].select(".aiv-reading-panel li a[href]")) >= 2:
            if path == "/":
                language = widget[0].find_previous_sibling()
                if not page.select_one("#sidebar-right #block-20 .aiv-social-box"):
                    raise RuntimeError("Widget social assente dalla posizione prevista in home.")
            else:
                sidebar = page.select_one("#sidebar-right")
                language = sidebar.select_one(".aiv-language")
                social = sidebar.select("#block-20:has(.aiv-social-box)")
                children = sidebar.find_all(recursive=False)
                adverts = [
                    node for node in children
                    if "av-autopilot-sidebar-widget" in node.get("class", [])
                    or node.get("id", "").startswith("av_sidebar_banner_")
                ]
                if (not language or len(social) != 1 or len(sidebar.select(".aiv-social-box")) != 1
                        or any(node not in children for node in (language, social[0], widget[0]))
                        or len(adverts) != 1 or widget[0].find_previous_sibling() != adverts[0]
                        or not children.index(language) < children.index(social[0]) < children.index(adverts[0])):
                    positions = [node.get("id") or node.get("class") or node.name for node in children]
                    raise RuntimeError(f"Ordine della barra laterale inatteso su {path}: {positions}")
                print(f"Widget Da leggere verificato subito sotto la pubblicità su {path}")
        else:
            raise RuntimeError(f"Widget letture mancante o incompleto su {path}")
        if not language or language.name != "details" or "aiv-language" not in language.get("class", []):
            raise RuntimeError(f"Selettore della lingua mancante su {path}")
        links = language.select("a[lang][href]")
        original = SITE + path
        if (not links or links[0]["lang"] != "it" or links[0]["href"] != original
                or links[0].get("data-original") != original):
            raise RuntimeError(f"Collegamento alla versione italiana mancante su {path}")
        languages = set()
        for link in links[1:]:
            url = urlsplit(link["href"])
            params = parse_qs(url.query)
            if (url.scheme, url.netloc, url.path) != ("https", "translate.google.com", "/translate") or params != {
                "sl": ["it"], "tl": [link["lang"]], "u": [original]
            }:
                raise RuntimeError(f"Destinazione di traduzione inattesa su {path}")
            languages.add(link["lang"])
        if len(links) != 9 or len(languages) != 8 or "it" in languages:
            raise RuntimeError(f"Elenco delle lingue incompleto su {path}")
        print(f"Menu lingua verificato su {path} — italiano e {len(languages)} traduzioni")


def verify_editorial_navigation(session):
    archive = get_page(session, ARCHIVE)
    overview = archive.select(".aiv-offers-overview")
    headings = {heading.get_text(" ", strip=True) for panel in overview for heading in panel.select("h2")}
    if (len(overview) != 1 or not {"Ultime selezioni", "Black Friday e campagne"} <= headings
            or not archive.select_one("#aiv-offers-archive")):
        raise RuntimeError("La navigazione delle offerte non è presente o completa.")
    print("Verificate le sezioni della pagina Offerte.")
    for path in ARTICLES:
        page = get_page(session, path)
        outline = page.select("main .aiv-article-outline")
        links = outline[0].select('a[href^="#"]') if len(outline) == 1 else []
        if len(links) < 3 or any(not page.find(id=unquote(link["href"][1:])) for link in links):
            raise RuntimeError(f"Indice mancante o collegamenti incompleti su {path}")
        print(f"Indice verificato su {path} — {len(links)} sezioni")


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


def deploy(admin, public, name, source, check, *, previous_hash=None):
    ensure_snippets_plugin(admin)
    code = source.read_text(encoding="utf-8").removeprefix("<?php\n")
    matches = [item for item in wp(admin, "GET", SNIPPETS) if item.get("name") == name]
    if len(matches) > 1:
        raise RuntimeError("Uno snippet con questo nome ha contenuto diverso dal repository.")
    before = matches[0] if matches else None
    update = before and before.get("code", "").strip() != code.strip()
    if update and sha256(before.get("code", "").strip().encode("utf-8")).hexdigest() != previous_hash:
        raise RuntimeError("Uno snippet con questo nome ha contenuto diverso dal repository.")
    if before and before["active"] and not update:
        check(public)
        return
    if not before:
        before = wp(admin, "POST", SNIPPETS, json={"name": name, "code": code, "scope": "front-end", "active": False})
    route = f"{SNIPPETS}/{int(before['id'])}"
    try:
        saved = wp(admin, "POST", route, json={"code": code, "active": False}) if update else before
        if saved.get("code", "").strip() != code.strip() or saved.get("code_error"):
            raise RuntimeError("Il contenuto dello snippet non è stato salvato correttamente.")
        wp(admin, "POST", route + "/activate")
        state = wp(admin, "GET", route)
        if not state.get("active"):
            state = wp(admin, "POST", route, json={"active": True})
        if not state.get("active") or state.get("code_error"):
            raise RuntimeError("WordPress non ha confermato l'attivazione dello snippet.")
        check(public)
    except (RuntimeError, requests.RequestException):
        wp(admin, "POST", route + "/deactivate")
        if update:
            wp(admin, "POST", route, json={"code": before["code"], "active": False})
            if before["active"]:
                wp(admin, "POST", route + "/activate")
            print("Versione precedente ripristinata dopo verifica fallita.")
        else:
            print("Snippet disattivato dopo verifica pubblica fallita.")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    variants = parser.add_mutually_exclusive_group()
    variants.add_argument("--related-cards", action="store_true")
    variants.add_argument("--reading-widget", action="store_true")
    variants.add_argument("--editorial-navigation", action="store_true")
    args = parser.parse_args()
    base = os.environ.get("WP_BASE_URL", "").rstrip("/").removesuffix("/wp-json")
    user, password = (os.environ.get(key, "") for key in ("WP_USERNAME", "WP_APP_PASSWORD"))
    if base != SITE or not user or not password:
        raise SystemExit("Configurazione WordPress AI Vision mancante.")
    with requests.Session() as admin, requests.Session() as public:
        admin.auth = (user, password)
        if args.editorial_navigation:
            deploy(admin, public, NAVIGATION_NAME, NAVIGATION_SOURCE, verify_editorial_navigation)
        elif args.reading_widget:
            deploy(admin, public, READING_NAME, READING_SOURCE, verify_reading_widget,
                   previous_hash=PREVIOUS_READING_HASH)
            from wp_publisher import WordPressClient, get_timezone
            now = datetime.now(get_timezone())
            days = Counter(WordPressClient(base, user, password, False).ai_cyber_publication_days(now))
            print("Calendario cybersicurezza dal giorno corrente:",
                  {day.isoformat(): total for day, total in sorted(days.items()) if day >= now.date()})
        elif args.related_cards:
            deploy(admin, public, RELATED_NAME, RELATED_SOURCE, verify_related_cards)
        else:
            deploy(admin, public, NAME, SOURCE, verify)


if __name__ == "__main__":
    main()
