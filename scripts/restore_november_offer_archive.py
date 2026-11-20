"""Restore the original editorial product descriptions in two archived editions."""
import argparse
import html
import json
import os
import subprocess
from datetime import timedelta
from pathlib import Path
from time import time

import requests
from bs4 import BeautifulSoup

from amazon_affiliate import DISCLOSURE, MARKER, product_asin
from amazon_promotions import Offer, expire_in_body, parse_utc, render_offers, spread_by_category
from wp_publisher import WordPressClient

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://aivision.altervista.org"
SOURCE = "ece36d0da88bab542c477e7175b8ae7f0076b9b4"
TARGETS = (
    (3003, "amazon-black-friday-2026-11-19-2", "black-friday"),
    (3006, "amazon-offerte-ordinarie-2026-11-19", "daily"),
)
NOTE = ('<p class="aivision-offer-archive"><strong>Selezione d’archivio del 19 novembre 2026.</strong> '
        'Per le promozioni attuali, consulta la <a href="/category/offerte-2/">sezione Offerte</a>.</p>')


def original_sections():
    raw = subprocess.check_output(
        ["git", "show", f"{SOURCE}:config/amazon-editorial-offers.json"], cwd=ROOT
    )
    for edition in json.loads(raw):
        checked = parse_utc(edition["checked_at"])
        expires = parse_utc(edition["expires_at"])
        offers = [Offer(product_asin(row["url"]), row["category"], row["title"], row["description"], row["why"],
                        "", row["url"], expires) for row in edition["products"]]
        if edition["kind"] == "black-friday":
            # The first edition already contained two products and took 18 more from this feed.
            first = {offer.key for offer in spread_by_category(offers)[:18]}
            offers = [offer for offer in offers if offer.key not in first]
        offers = spread_by_category(offers)[:20]
        if len({offer.key for offer in offers if offer.key}) != 20:
            raise ValueError("La selezione originale non contiene 20 prodotti distinti.")
        expected = expire_in_body(render_offers(offers, checked), expires + timedelta(seconds=1))
        sections = [f'<div class="{MARKER}">', f"<p>{DISCLOSURE}</p>", NOTE, "<h2>Scelte da AI Vision per voi</h2>"]
        for category in dict.fromkeys(offer.category for offer in offers):
            sections.append(f"<h3>{html.escape(category)}</h3>")
            for offer in (item for item in offers if item.category == category):
                sections.extend((f"<h4>{html.escape(offer.title)}</h4>",
                                 f"<p>{html.escape(offer.description)}</p>",
                                 f"<p><strong>Cosa controllare.</strong> {html.escape(offer.why)}</p>"))
        yield edition["kind"], (expected, "\n".join([*sections, "</div>"]))


def read_post(client, post_id, slug):
    response = client.session.get(client._url(f"posts/{post_id}"), params={"context": "edit"}, timeout=30)
    response.raise_for_status()
    post = response.json()
    if post["id"] != post_id or post["slug"] != slug or post["status"] != "publish":
        raise ValueError(f"Identità inattesa per l’articolo {post_id}.")
    return post


def planned_content(body, old, new):
    if body.count(new) == 1:
        return body
    if body.count(old) != 1:
        raise ValueError("La struttura archiviata su WordPress è diversa dalla selezione originale.")
    return body.replace(old, new, 1)


def verify_public(slug):
    response = requests.get(f"{SITE}/{slug}/", params={"aivision_archive_check": int(time())}, timeout=45)
    response.raise_for_status()
    page = BeautifulSoup(response.content, "html.parser")
    note = page.select_one(".aivision-offer-archive")
    if not note:
        raise RuntimeError(f"Nota di archivio assente su {slug}.")
    section = note.parent
    if (len(section.select("h4")) != 20 or section.select(".aivision-amazon-price, img")
            or "Questa offerta è terminata" in section.get_text()):
        raise RuntimeError(f"Selezione incompleta su {slug}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    base, user, password = (os.environ.get(k, "") for k in ("WP_BASE_URL", "WP_USERNAME", "WP_APP_PASSWORD"))
    if base.rstrip("/").removesuffix("/wp-json") != SITE or not user or not password:
        raise ValueError("Configurazione WordPress AI Vision mancante.")
    client = WordPressClient(base, user, password, not args.apply)
    sources = dict(original_sections())
    plans = []
    for post_id, slug, kind in TARGETS:
        post = read_post(client, post_id, slug)
        try:
            body = planned_content(post["content"]["raw"], *sources[kind])
        except ValueError as exc:
            raise ValueError(f"{slug}: {exc}") from exc
        plans.append((post, body))
        print(f"{slug}: struttura verificata per 20 schede originali.")
    if not args.apply:
        return
    for post, body in plans:
        post_id, slug = post["id"], post["slug"]
        if body != post["content"]["raw"]:
            fresh = read_post(client, post_id, slug)
            if fresh["content"]["raw"] != post["content"]["raw"]:
                raise RuntimeError(f"{slug}: contenuto modificato durante il controllo.")
            response = client.session.post(client._url(f"posts/{post_id}"), params={"context": "edit"},
                                           json={"content": body}, timeout=30)
            response.raise_for_status()
        saved = read_post(client, post_id, slug)
        if (saved["content"]["raw"] != body
                or any(saved[key] != post[key] for key in ("title", "featured_media", "date_gmt"))):
            raise RuntimeError(f"{slug}: modifica WordPress da verificare.")
        verify_public(slug)
        print(f"{slug}: archivio pubblico verificato, 20 schede e una nota unica.")


if __name__ == "__main__":
    main()
