#!/usr/bin/env python3
"""Remove stock AI cover captions and refresh the first Amazon offer editions."""
from __future__ import annotations

import argparse
import collections
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from amazon_affiliate import configured_tag
from amazon_promotions import cover_label, editorial_picks, picks_section
from inline_image_repair import ATTACHMENT_CLASS, leading_cover, request_with_retry
from wp_public_cleanup import API, FIELDS, content_hash, read_posts, wp_session, write_json
from wp_publisher import WordPressClient, featured_image_block, get_timezone

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "data/offer_refresh_plan.json"
BACKUP = ROOT / "data/offer_refresh_public_backups.json"
REPORT = ROOT / "data/offer_refresh_result.json"
MEDIA = API.rsplit("/", 1)[0] + "/media"
LABEL = "Illustrazione generata con IA"
TAGS = re.compile(r"<[^>]*>")
BLOCKS = re.compile(r"<(figcaption|p)\b[^>]*>([^<>]*(?:<(?:strong|em|span|/strong|/em|/span)\b[^>]*>[^<>]*)*)</\1>",
                    re.IGNORECASE | re.DOTALL)
PARAGRAPH = re.compile(r"<!-- wp:paragraph(?: [^>]*)? -->\s*<!-- /wp:paragraph -->\s*")
SEARCH_F25 = re.compile(r'<div class="av-amazon-affiliate">(?:(?!</div>).)*'
                        r'amazon\.it/s\?k=Roborock\+F25\+Steam(?:(?!</div>).)*</div>', re.S)
EDITIONS = {
    2878: ("offerte-amazon-del-giorno-2026-11-18", "reading-2026-11", "lettura", "Offerte del giorno"),
    2881: ("amazon-black-friday-2026-11-19", "black-friday-2026", "black-friday", "Black Friday"),
    2786: ("quale-roborock-scegliere-offerte-black-friday", "roborock-2026", "", ""),
}
OLD_MEDIA = {2878: 2877, 2881: 2880}
MARKER = "<!-- aivision-product-picks -->"
MEDIA_FIELDS = "id,caption,description,alt_text"


def plain(value: str) -> str:
    return " ".join(html.unescape(TAGS.sub("", value)).split())


def exact_credit(value: str) -> bool:
    return plain(value).rstrip(".").casefold() == LABEL.casefold()


def strip_credit(content: str) -> str:
    cleaned = BLOCKS.sub(lambda m: "" if exact_credit(m[2]) else m[0], content)
    return PARAGRAPH.sub("", cleaned) if cleaned != content else cleaned


def media_changes(row: dict) -> dict:
    changes = {}
    for key in ("caption", "description"):
        original = row[key]["raw"]
        clean = "" if exact_credit(original) else strip_credit(original)
        if clean != original:
            changes[key] = clean
    if exact_credit(row["alt_text"]):
        changes["alt_text"] = ""
    return changes


def find_media(session) -> list[dict]:
    params = {"context": "edit", "search": LABEL, "_fields": MEDIA_FIELDS, "per_page": 50}
    result = []
    for page in range(1, 101):
        response = request_with_retry(session, "get", MEDIA, params={**params, "page": page})
        batch = response.json()
        result.extend(row for row in batch if media_changes(row))
        pages = response.headers.get("X-WP-TotalPages")
        if (pages and page >= int(pages)) or (not pages and len(batch) < 50):
            return result
    raise RuntimeError("Inventario media incompleto.")


def build_plan(session) -> None:
    posts = read_posts(session)
    tag = configured_tag()
    now = datetime.now(get_timezone())
    rows = []
    for post in posts:
        original = post["content"]["raw"]
        content = strip_credit(original)
        config = EDITIONS.get(post["id"])
        cover = ""
        label = ""
        if config and post["slug"] == config[0]:
            _, group, asset, label = config
            cover = asset if post["featured_media"] == OLD_MEDIA.get(post["id"]) else ""
            if MARKER not in content:
                section = picks_section(editorial_picks(group, now, tag), now,
                                        disclosure="av-amazon-affiliate" not in content or post["id"] == 2786)
                if section:
                    if post["id"] == 2786:
                        content = SEARCH_F25.sub("", content)
                    content += "\n" + section
        if content != original or cover:
            rows.append({"base": post, "content": content, "asset": cover, "label": label})
    media = find_media(session)
    count = collections.Counter(post["status"] for post in posts)
    write_json(BACKUP, {
        "posts": [
            {"post_id": row["base"]["id"], "status": row["base"]["status"],
             "featured_media": row["base"]["featured_media"],
             "hash": content_hash(row["base"]["content"]["raw"]),
             **({"content": row["base"]["content"]["raw"]} if row["base"]["status"] == "publish" else {})}
            for row in rows
        ],
        "media_ids": [row["id"] for row in media],
    })
    write_json(PLAN, {"posts": rows, "media": media})
    print(f"Piano: {dict(count)}, {len(rows)} articoli da aggiornare, {len(media)} allegati da ripulire.")


def refresh_post(row: dict) -> dict:
    base = row["base"]
    session = wp_session()
    params = {"context": "edit", "_fields": FIELDS}
    endpoint = f"{API}/{base['id']}"
    current = request_with_retry(session, "get", endpoint, params=params).json()
    fixed = ("title", "slug", "status", "date", "date_gmt", "featured_media")
    if current["content"]["raw"] != base["content"]["raw"] or any(current[key] != base[key] for key in fixed):
        raise RuntimeError("Articolo modificato dopo il controllo.")
    content = row["content"]
    payload = {}
    if row["asset"]:
        cover, _ = leading_cover(content)
        match = ATTACHMENT_CLASS.search(cover[0]) if cover else None
        if match is None or int(match[1]) != current["featured_media"]:
            raise RuntimeError("Copertina nel testo diversa da quella in evidenza.")
        root, _, _ = API.partition("/wp-json")
        client = WordPressClient(root, "", "", False)
        client.session = session
        filename = f"ai-vision-offerte-{base['id']}-editoriale"
        existing = request_with_retry(session, "get", MEDIA,
                                      params={"context": "edit", "slug": filename, "_fields": "id,source_url,alt_text"}).json()
        title = base["title"]["raw"]
        if existing:
            media = existing[0]
        else:
            source = ROOT / "assets" / "amazon-covers" / (row["asset"] + ".jpg")
            media = client.upload_media(cover_label(source.read_bytes(), row["label"]),
                                        filename + ".jpg", "image/jpeg", title, "")
        content = featured_image_block(media, title) + content[cover.end():].lstrip()
        payload["featured_media"] = media["id"]
    payload["content"] = content
    request_with_retry(session, "post", endpoint, params=params, json=payload, allow_redirects=False)
    saved = request_with_retry(session, "get", endpoint, params=params).json()
    if (saved["content"]["raw"] != content
            or saved["featured_media"] != payload.get("featured_media", base["featured_media"])
            or any(saved[key] != base[key] for key in ("title", "slug", "status", "date", "date_gmt"))):
        raise RuntimeError("Modifica WordPress da verificare.")
    return {"id": base["id"], "status": saved["status"], "cover": payload.get("featured_media"),
            "new_picks": MARKER in content and MARKER not in base["content"]["raw"]}


def refresh_media(row: dict) -> dict:
    session = wp_session()
    endpoint = f"{MEDIA}/{row['id']}"
    params = {"context": "edit", "_fields": MEDIA_FIELDS}
    current = request_with_retry(session, "get", endpoint, params=params).json()
    payload = media_changes(current)
    if payload:
        request_with_retry(session, "post", endpoint, params=params, json=payload, allow_redirects=False)
        verified = request_with_retry(session, "get", endpoint, params=params).json()
        if media_changes(verified):
            raise RuntimeError("Didascalia WordPress ancora presente.")
    return {"id": row["id"], "updated": bool(payload)}


def apply(session) -> int:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    result = {"posts": [], "media": [], "errors": []}
    for kind, action in (("posts", refresh_post), ("media", refresh_media)):
        with ThreadPoolExecutor(max_workers=4) as pool:
            tasks = {pool.submit(action, row): row["id"] if kind == "media" else row["base"]["id"]
                     for row in plan[kind]}
            for task in as_completed(tasks):
                try:
                    result[kind].append(task.result())
                except Exception as exc:
                    result["errors"].append({"type": kind, "id": tasks[task], "error": str(exc)})
    posts = read_posts(session)
    result["remaining_credit_posts"] = [
        p["id"] for p in posts if strip_credit(p["content"]["raw"]) != p["content"]["raw"]
    ]
    result["remaining_credit_media"] = [m["id"] for m in find_media(session)]
    write_json(REPORT, result)
    states = collections.Counter(post["status"] for post in result["posts"])
    print(f"Verificati {dict(states)}, {len(result['media'])} allegati, "
          f"{sum(row['cover'] is not None for row in result['posts'])} copertine, "
          f"{sum(row['new_picks'] for row in result['posts'])} schede aggiunte ad articoli.")
    print(f"Didascalie residue articolo: {result['remaining_credit_posts']}; "
          f"allegati: {result['remaining_credit_media']}; errori: {result['errors']}")
    return int(bool(result["errors"] or result["remaining_credit_posts"] or result["remaining_credit_media"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    session = wp_session()
    if not session.auth:
        raise PermissionError("Credenziali WordPress necessarie per verificare allegati e programmati.")
    if args.apply:
        return apply(session)
    build_plan(session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
