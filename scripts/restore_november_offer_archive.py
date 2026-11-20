"""Restore editorial descriptions and direct product links in the 19 November editions."""
import argparse
import html
import json
import os
import re
import subprocess
from pathlib import Path
from time import time

import requests
from bs4 import BeautifulSoup

from amazon_affiliate import DISCLOSURE, MARKER, configured_tag, product_asin
from amazon_promotions import AMAZON, Offer, affiliate_url, parse_utc, render_offers, spread_by_category
from wp_publisher import WordPressClient

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://aivision.altervista.org"
SOURCE = "ece36d0da88bab542c477e7175b8ae7f0076b9b4"
TARGETS = (
    (2983, "amazon-black-friday-2026-11-19-1", "black-friday-first"),
    (3003, "amazon-black-friday-2026-11-19-2", "black-friday"),
    (3006, "amazon-offerte-ordinarie-2026-11-19", "daily"),
)
LEGACY_MARKER = re.compile(r"<!-- aivision-amazon-promo [^ <>]+ -->.*?<!-- /aivision-amazon-promo -->", re.S)
LEGACY_NOTICE = "<p>Questa offerta è terminata. Prezzo e disponibilità possono essere diversi da quelli della pubblicazione.</p>"
NOTE = ('<p class="aivision-offer-archive"><strong>Selezione d’archivio del 19 novembre 2026.</strong> '
        'Per le promozioni attuali, consulta la <a href="/category/offerte-2/">sezione Offerte</a>.</p>')


def render_archive(offers, tag, heading, disclosure, note):
    sections = [f'<div class="{MARKER}">']
    if disclosure:
        sections.append(f"<p>{DISCLOSURE}</p>")
    if note:
        sections.append(NOTE)
    sections.append(f"<h2>{heading}</h2>")
    for category in dict.fromkeys(offer.category for offer in offers):
        sections.append(f"<h3>{html.escape(category)}</h3>")
        for offer in (item for item in offers if item.category == category):
            sections.extend((f"<h4>{html.escape(offer.title)}</h4>",
                             f"<p>{html.escape(offer.description)}</p>",
                             f"<p><strong>Cosa controllare.</strong> {html.escape(offer.why)}</p>"))
            if tag:
                url = html.escape(affiliate_url(f"{AMAZON}/dp/{offer.key}", tag), quote=True)
                sections.append(f'<p><a href="{url}" rel="sponsored nofollow">Vedi il prodotto su Amazon</a></p>')
    return "\n".join([*sections, "</div>"])


def historical_config(filename):
    return json.loads(subprocess.check_output(["git", "show", f"{SOURCE}:config/{filename}"], cwd=ROOT))


def archive_section(offers, checked, tag, *, heading="Scelte da AI Vision per voi", disclosure=True, note=True):
    expected = LEGACY_MARKER.sub(LEGACY_NOTICE, render_offers(offers, checked, heading=heading, disclosure=disclosure))
    archived = render_archive(offers, "", heading, disclosure, note)
    linked = render_archive(offers, tag, heading, disclosure, note)
    return expected, archived, linked, {offer.key for offer in offers if offer.key}


def historical_offers(rows, expires):
    return [Offer(product_asin(row["url"]), row["category"], row["title"], row["description"], row["why"],
                  "", row["url"], expires) for row in rows]


def original_sections(tag):
    for edition in historical_config("amazon-editorial-offers.json"):
        checked = parse_utc(edition["checked_at"])
        expires = parse_utc(edition["expires_at"])
        offers = historical_offers(edition["products"], expires)
        if edition["kind"] == "black-friday":
            # The first edition already contained two products and took 18 more at 22:55.
            reviewed = historical_config("amazon-reviewed-editions.json")["2026-11-19"]
            first = spread_by_category(offers)[:18]
            yield "black-friday-first", (
                archive_section(historical_offers(reviewed["products"], expires), checked, tag,
                                heading="I prodotti segnalati"),
                archive_section(first, checked, tag, heading="Aggiornamento delle 22:55", disclosure=False, note=False),
            )
            used = {offer.key for offer in first}
            offers = [offer for offer in offers if offer.key not in used]
        offers = spread_by_category(offers)[:20]
        yield edition["kind"], (archive_section(offers, checked, tag),)


def read_post(client, post_id, slug):
    response = client.session.get(client._url(f"posts/{post_id}"), params={"context": "edit"}, timeout=30)
    response.raise_for_status()
    post = response.json()
    if post["id"] != post_id or post["slug"] != slug or post["status"] != "publish":
        raise ValueError(f"Identità inattesa per l’articolo {post_id}.")
    return post


def planned_content(body, legacy, archived, new):
    if body.count(new) == 1:
        return body
    for old in (archived, legacy):
        if body.count(old) == 1:
            return body.replace(old, new, 1)
    raise ValueError("La struttura archiviata su WordPress è diversa dalla selezione originale.")


def verify_public(slug, product_ids):
    response = requests.get(f"{SITE}/{slug}/", params={"aivision_archive_check": int(time())}, timeout=45)
    response.raise_for_status()
    page = BeautifulSoup(response.content, "html.parser")
    sections = page.select(f"div.{MARKER}")
    linked = [asin for section in sections for link in section.select("a[href]") if (asin := product_asin(link["href"]))]
    if (len(page.select(".aivision-offer-archive")) != 1 or len(linked) != 20 or set(linked) != product_ids
            or sum(len(section.select("h4")) for section in sections) != 20
            or any(section.select(".aivision-amazon-price, img") or "Questa offerta è terminata" in section.get_text()
                   for section in sections)):
        raise RuntimeError(f"Selezione incompleta su {slug}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    base, user, password = (os.environ.get(k, "") for k in ("WP_BASE_URL", "WP_USERNAME", "WP_APP_PASSWORD"))
    if base.rstrip("/").removesuffix("/wp-json") != SITE or not user or not password:
        raise ValueError("Configurazione WordPress AI Vision mancante.")
    tag = configured_tag()
    if not tag:
        raise ValueError("Tracking ID Amazon Italia mancante.")
    client = WordPressClient(base, user, password, not args.apply)
    sources = dict(original_sections(tag))
    plans = []
    for post_id, slug, kind in TARGETS:
        post = read_post(client, post_id, slug)
        body = post["content"]["raw"]
        product_ids = set()
        try:
            for legacy, archived, new, ids in sources[kind]:
                body = planned_content(body, legacy, archived, new)
                product_ids.update(ids)
            if len(product_ids) != 20:
                raise ValueError("La selezione originale non contiene 20 prodotti distinti.")
        except ValueError as exc:
            raise ValueError(f"{slug}: {exc}") from exc
        plans.append((post, body, product_ids))
        print(f"{slug}: struttura verificata per 20 schede originali.")
    if not args.apply:
        return
    for post, body, product_ids in plans:
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
        verify_public(slug, product_ids)
        print(f"{slug}: archivio pubblico verificato, 20 schede con link prodotto e una nota unica.")


if __name__ == "__main__":
    main()
