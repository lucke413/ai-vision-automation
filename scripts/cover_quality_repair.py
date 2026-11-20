#!/usr/bin/env python3
"""Audit live covers and correct the exposure of identifiable AI Vision images."""

from __future__ import annotations

import argparse
import io
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import local
from urllib.parse import urlsplit

import requests
from PIL import Image

if __package__:
    from .cover_media import AI_CREDIT, cover_exposure, encode_cover_jpeg, grade_ai_cover, is_retired_cover
    from .inline_image_repair import ATTACHMENT_CLASS, IMAGE_SRC, fetch_all_posts, leading_cover, media_path, raw_content, raw_title, request_with_retry, wp_media_url, write_json_atomic
    from .wp_publisher import USER_AGENT, WordPressClient, read_image_response, slugify
else:
    from cover_media import AI_CREDIT, cover_exposure, encode_cover_jpeg, grade_ai_cover, is_retired_cover
    from inline_image_repair import ATTACHMENT_CLASS, IMAGE_SRC, fetch_all_posts, leading_cover, media_path, raw_content, raw_title, request_with_retry, wp_media_url, write_json_atomic
    from wp_publisher import USER_AGENT, WordPressClient, read_image_response, slugify


REPORT = Path(__file__).resolve().parents[1] / "data" / "cover_quality_report.json"
IMAGE_BLOCK_ID = re.compile(r'("id"\s*:\s*)\d+')
# This is when the repository's 1200×675 DreamShaper publisher went live.
DREAMSHAPER_START = "2026-11-18"
WP_FIELDS = "id,status,date,date_gmt,slug,modified,featured_media,content"


def generated_cover(post: dict, media: dict, block: str, image: Image.Image) -> bool:
    caption = media.get("caption") or {}
    provenance = str(caption.get("raw") or caption.get("rendered") or "") + block
    if "creativecommon" in provenance.casefold() or "fonte foto" in provenance.casefold():
        return False
    if AI_CREDIT.casefold() in provenance.casefold():
        return True
    if caption.get("raw", caption.get("rendered", "")).strip():
        return False
    filename = Path(urlsplit(media.get("source_url", "")).path).stem
    if filename.startswith(("ai-vision-offerte-", "ai-vision-reading-")):
        return True
    # Before that deployment, some uncredited images came from other sources.
    title_filename = slugify(raw_title(post))
    return (post.get("date", "") >= DREAMSHAPER_START and image.size == (1200, 675)
            and (filename == title_filename or re.fullmatch(re.escape(title_filename) + r"-\d+", filename) is not None))


def fetch_image(url: str, client: WordPressClient) -> Image.Image:
    if not wp_media_url(url, client):
        raise ValueError("URL della copertina fuori dagli allegati del sito")
    headers = {"User-Agent": USER_AGENT, "Referer": client.base_url + "/"}
    with request_with_retry(requests, "get", url, headers=headers, stream=True) as response:
        data = read_image_response(response)
    if not data:
        raise ValueError("File immagine vuoto o troppo grande")
    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > 24_000_000:
            raise ValueError("Dimensioni della copertina anomale")
        return image.copy()


def update_cover(client: WordPressClient, post: dict, media: dict, image: Image.Image, block) -> int:
    post_id, previous_id = post["id"], media["id"]
    url = client._url(f"posts/{post_id}")
    params = {"context": "edit", "_fields": WP_FIELDS}
    before = request_with_retry(client.session, "get", url, params=params).json()
    original = raw_content(post)
    if (before.get("modified") != post.get("modified") or raw_content(before) != original
            or before.get("featured_media") != previous_id):
        raise ValueError("Copertina o articolo cambiati durante il controllo")

    filename = f"ai-vision-light-v2-{post_id}-{previous_id}"
    prior_uploads = request_with_retry(client.session, "get", client._url("media"),
                                      params={"slug": filename, "context": "edit", "_fields": "id,source_url"}).json()
    replacement = next((value for value in prior_uploads if wp_media_url(value.get("source_url", ""), client)), None)
    if replacement is None:
        alt = str(media.get("alt_text") or raw_title(post))
        replacement = client.upload_media(encode_cover_jpeg(image), filename + ".jpg", "image/jpeg", alt, AI_CREDIT)
    new_id = int(replacement["id"])
    new_url = replacement["source_url"]
    if not wp_media_url(new_url, client):
        raise ValueError("URL della nuova copertina non valido")

    payload = {"featured_media": new_id}
    if block:
        figure = IMAGE_SRC.sub(lambda m: m[0].replace(m[2], new_url, 1), block[0], count=1)
        figure = ATTACHMENT_CLASS.sub(f"wp-image-{new_id}", figure, count=1)
        figure = IMAGE_BLOCK_ID.sub(lambda m: m[1] + str(new_id), figure, count=1)
        payload["content"] = original[:block.start()] + figure + original[block.end():]
    current = request_with_retry(client.session, "get", url, params=params).json()
    before_write = ("status", "date", "date_gmt", "slug", "modified", "featured_media")
    if any(before.get(field) != current.get(field) for field in before_write) or raw_content(current) != original:
        raise ValueError("Articolo modificato prima del salvataggio")
    request_with_retry(client.session, "post", url, params=params, json=payload)
    saved = request_with_retry(client.session, "get", url, params=params).json()
    if (saved.get("featured_media") != new_id or raw_content(saved) != payload.get("content", original)
            or any(saved.get(field) != current.get(field) for field in ("date", "date_gmt", "slug"))
            or (saved.get("status") != current.get("status")
                and (current.get("status"), saved.get("status")) != ("future", "publish"))):
        raise ValueError("Controllo WordPress dopo il salvataggio fallito")
    return new_id


def inspect_post(client: WordPressClient, post: dict, apply: bool) -> dict:
    media_id = post.get("featured_media") or 0
    row = {"id": post["id"], "status": post["status"], "previous_media": media_id}
    media = next((value for value in post.get("_embedded", {}).get("wp:featuredmedia", [])
                  if value.get("id") == media_id), {})
    source_url = media.get("source_url", "")
    if not source_url:
        return {**row, "result": "missing"}
    if Path(urlsplit(source_url).path).name.startswith(f"ai-vision-light-v2-{post['id']}-"):
        return {**row, "result": "already_updated"}
    img = fetch_image(source_url, client)
    if is_retired_cover(img):
        return {**row, "result": "retired"}
    exposure = cover_exposure(img)
    row["exposure"] = exposure.median
    if not exposure.dark:
        return {**row, "result": "ok"}
    block, inline_url = leading_cover(raw_content(post))
    if not generated_cover(post, media, block[0] if block else "", img):
        return {**row, "result": "needs_editorial_review"}
    if block and (media_path(inline_url) != media_path(source_url) or re.search(r"\bsrcset=|<a\b", block[0], re.I)):
        return {**row, "result": "different_inline"}
    corrected = grade_ai_cover(img)
    revised = cover_exposure(corrected)
    if not revised.usable or revised.median - exposure.median < 12:
        return {**row, "result": "needs_new_image"}
    row["new_exposure"] = revised.median
    if not apply:
        return {**row, "result": "candidate"}
    new_id = update_cover(client, post, media, corrected, block)
    return {**row, "result": "updated", "new_media": new_id}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--scheduled-only", action="store_true")
    args = parser.parse_args()
    credentials = [os.environ.get(name, "").strip() for name in ("WP_BASE_URL", "WP_USERNAME", "WP_APP_PASSWORD")]
    if not all(credentials):
        parser.error("Configurazione WordPress incompleta")
    client = WordPressClient(*credentials, dry_run=not args.apply)
    worker = local()

    def inspect(post):
        if not hasattr(worker, "client"):
            worker.client = WordPressClient(*credentials, dry_run=not args.apply)
        try:
            return inspect_post(worker.client, post, args.apply)
        except requests.RequestException as exc:
            code = exc.response.status_code if exc.response is not None else "rete"
            return {"id": post["id"], "status": post["status"], "result": "fetch_error", "error": str(code)}
        except (OSError, ValueError, TypeError, RuntimeError, KeyError) as exc:
            return {"id": post["id"], "status": post["status"], "result": "error", "error": type(exc).__name__}

    results = []
    for status in (("future",) if args.scheduled_only else ("future", "publish")):
        posts = fetch_all_posts(client, statuses=(status,))
        with ThreadPoolExecutor(max_workers=6) as pool:
            rows = list(pool.map(inspect, posts))
        results += rows
        totals = Counter(row["result"] for row in rows)
        print(f"{status}: {len(rows)} copertine. {dict(totals)}", flush=True)
        for row in rows:
            if row["result"] not in {"ok", "already_updated"}:
                print(f"#{row['id']} {status} {row['result']}" +
                      (f" {row['previous_media']} -> {row['new_media']}" if row["result"] == "updated" else ""), flush=True)
        write_json_atomic(REPORT, {"apply": args.apply, "items": results})
    return int(any(row["result"] in {"error", "fetch_error"} for row in results))


if __name__ == "__main__":
    raise SystemExit(main())
