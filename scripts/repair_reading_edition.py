"""Correct the published reading edition of 19 November without changing its permalink."""
import os
from pathlib import Path

from amazon_promotions import cover_label
from inline_image_repair import leading_cover
from wp_publisher import WordPressClient, featured_image_block

TITLE = "Mese della Lettura su Amazon: tre libri da scoprire e la selezione eBook Kindle"
INTRO = ("Dal 19 novembre, una selezione per chi cerca la prossima lettura: un romanzo italiano, "
         "un fantasy e un albo illustrato, con il link alla promozione sugli eBook Kindle.")
SLUG = "offerte-amazon-del-giorno-2026-11-19"


def correct():
    client = WordPressClient(*(os.environ[k] for k in ("WP_BASE_URL", "WP_USERNAME", "WP_APP_PASSWORD")), False)
    endpoint = client._url("posts/2969")
    response = client.session.get(endpoint, params={"context": "edit"}, timeout=30)
    response.raise_for_status()
    post = response.json()
    if post["slug"] != SLUG or post["status"] != "publish":
        raise ValueError("Articolo atteso assente")
    if post["title"]["raw"] == TITLE:
        return
    if post["featured_media"] != 2968 or "Black Friday" not in post["title"]["raw"]:
        raise ValueError("Edizione cambiata dopo il controllo")
    raw = post["content"]["raw"]
    first, _ = leading_cover(raw)
    if not first:
        raise ValueError("Copertina iniziale assente")
    sections = raw.index("<h3>Narrativa italiana</h3>")
    start = raw.index("<h3>Lettura</h3>", sections)
    end = raw.index("<h3>Lettura digitale</h3>", start)
    body = raw[first.end():sections]
    begin = body.index("<p>La selezione di oggi")
    finish = body.index("</p>", begin)
    body = body[:begin] + "<p>" + INTRO + body[finish:]
    body = body.replace("Scelte da AI Vision per voi", "Libri ed eBook da scoprire")
    filename = "mese-della-lettura-amazon-19-novembre-2026"
    result = client.session.get(client._url("media"), params={"slug": filename}, timeout=30)
    result.raise_for_status()
    media = result.json()
    if not media:
        image = Path(__file__).resolve().parents[1] / "assets/amazon-covers/lettura.jpg"
        media = [client.upload_media(cover_label(image.read_bytes(), "MESE DELLA LETTURA"),
                                     filename + ".jpg", "image/jpeg", "Libri ed e-reader per il Mese della Lettura", "")]
    content = featured_image_block(media[0], TITLE) + body + raw[sections:start] + raw[end:]
    response = client.session.post(endpoint, params={"context": "edit"}, timeout=30, json={
        "title": TITLE, "excerpt": INTRO, "content": content, "featured_media": media[0]["id"],
        "aivision_seo": {"seo_title": TITLE, "seo_description": INTRO, "focus_keyphrase": "Mese della Lettura su Amazon"}})
    response.raise_for_status()
    saved = response.json()
    if saved["title"]["raw"] != TITLE or saved["featured_media"] != media[0]["id"] or "Black Friday" in saved["content"]["raw"]:
        raise RuntimeError("Verificare la modifica WordPress")


if __name__ == "__main__":
    correct()
