#!/usr/bin/env python3
"""Sostituisce le copertine a bande e ripristina le copertine mancanti."""
from __future__ import annotations

import html
import io
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import local
from urllib.parse import unquote, urlsplit

import requests
from PIL import Image

if __package__:
    from .cover_media import CoverCredit, generate_ai_cover, is_interim_card, is_retired_cover, is_striped_cover
    from .wp_publisher import PublisherError, USER_AGENT, WordPressClient, featured_image_block, read_image_response
else:
    from cover_media import CoverCredit, generate_ai_cover, is_interim_card, is_retired_cover, is_striped_cover
    from wp_publisher import PublisherError, USER_AGENT, WordPressClient, featured_image_block, read_image_response

ROOT = Path(__file__).resolve().parent.parent
BACKUP_PATH = ROOT / "data" / "inline_image_repair_backup.json"
REPORT_PATH = ROOT / "data" / "inline_image_repair_report.json"
PER_PAGE = 100
UPGRADE_DIR = ROOT / "assets" / "cover-upgrades"


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def request_with_retry(session, method: str, url: str, **kwargs):
    last_error = None
    for attempt in range(1, 5):
        try:
            response = getattr(session, method)(url, timeout=(8, 45), **kwargs)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_error = exc
        else:
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
        if attempt < 4:
            time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(f"Richiesta WordPress fallita dopo 4 tentativi: {url}") from last_error


def raw_content(post: dict) -> str:
    value = post.get("content")
    if isinstance(value, dict):
        return str(value.get("raw") or value.get("rendered") or "")
    return str(value or "")


IMAGE_MARKUP = r"(?:<figure\b(?:(?!</?figure\b).)*</figure>|<img\b[^>]*>)"
LEADING_IMAGE = re.compile(
    rf"^\s*(?:<!--\s*wp:image\b(?:(?!-->).)*-->\s*{IMAGE_MARKUP}\s*<!--\s*/wp:image\s*-->|{IMAGE_MARKUP})",
    re.IGNORECASE | re.DOTALL,
)
IMAGE_SRC = re.compile(r"""<img\b[^>]*?\s+src\s*=\s*(["'])([^"']+)\1""", re.IGNORECASE)
ATTACHMENT_CLASS = re.compile(r"\bwp-image-(\d+)\b")


def leading_cover(content: str):
    block = LEADING_IMAGE.match(content)
    image = IMAGE_SRC.search(block.group()) if block else None
    return (block, html.unescape(image.group(2))) if image else (None, "")


def raw_title(post: dict) -> str:
    value = post.get("title") or {}
    title = value.get("raw") or value.get("rendered") if isinstance(value, dict) else value
    return html.unescape(str(title or ""))


def fetch_all_posts(client: WordPressClient) -> list[dict]:
    posts: list[dict] = []
    for status in ("publish", "future"):
        page = 1
        while True:
            response = request_with_retry(
                client.session,
                "get",
                client._url("posts"),
                params={
                    "status": status,
                    "context": "edit",
                    "per_page": PER_PAGE,
                    "page": page,
                    "orderby": "date",
                    "order": "desc",
                    "_embed": "wp:featuredmedia",
                    "_fields": "id,title,status,date,modified,featured_media,content,meta,link,categories,_links,_embedded",
                },
            )
            batch = response.json()
            if not isinstance(batch, list):
                raise RuntimeError(f"Risposta inattesa da WordPress ({status}, pagina {page}).")
            posts.extend(item for item in batch if isinstance(item, dict))
            total_pages = int(response.headers.get("X-WP-TotalPages") or 0)
            if total_pages:
                if page >= total_pages:
                    break
            elif len(batch) < PER_PAGE:
                break
            page += 1
            if page > 100:
                raise RuntimeError("Paginazione WordPress anomala: interruzione di sicurezza.")
    unique = {}
    for post in posts:
        unique[post.get("id")] = post
    return list(unique.values())

def fetch_media(client: WordPressClient, media_id: int) -> dict:
    response = client.session.get(
        client._url(f"media/{media_id}"),
        params={"context": "edit", "_fields": "id,source_url,alt_text,mime_type,media_details"},
        timeout=30,
    )
    if response.status_code in (404, 410):
        return {}
    response.raise_for_status()
    return response.json()


def wp_media_url(url: str, client: WordPressClient) -> bool:
    parts = urlsplit(url)
    return (
        parts.scheme == "https"
        and parts.netloc == urlsplit(client.base_url).netloc
        and "/wp-content/uploads/" in parts.path
    )


def media_path(url: str) -> str:
    path = unquote(urlsplit(url).path)
    return re.sub(r"-\d+x\d+(?=\.[^./]+$)", "", path)


def image_state(url: str, client: WordPressClient, details: dict | None = None) -> str:
    if not wp_media_url(url, client):
        return "unknown" if url else "missing"
    details = details or {}
    width, height = details.get("width"), details.get("height")
    if width and height and (width < 300 or abs(width / height - 16 / 9) > .02 or
                             (details.get("filesize") or 0) > 220_000):
        return "ok"
    headers = {"User-Agent": USER_AGENT, "Referer": client.base_url.rstrip("/") + "/"}
    for attempt in range(3):
        try:
            with requests.get(
                url, headers=headers, stream=True, timeout=(5, 12),
                params={"av-cover-check": str(attempt)} if attempt else None,
            ) as response:
                if response.status_code in (404, 410):
                    return "missing"
                response.raise_for_status()
                content = read_image_response(response)
            break
        except requests.RequestException as exc:
            if attempt == 2 or (exc.response is not None and exc.response.status_code not in
                                {403, 429, 500, 502, 503, 504}):
                raise
            time.sleep(2 ** attempt)
    if not content:
        return "unknown"
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            if is_interim_card(image):
                return "previous_illustration"
            return "striped" if is_striped_cover(image) else "ok"
    except (OSError, ValueError, Image.DecompressionBombError):
        return "invalid"


@dataclass
class CoverRepair:
    media: dict
    replace_span: tuple[int, int] | None
    featured_state: str
    inline_state: str


def plan_repair(client: WordPressClient, post: dict) -> CoverRepair | None:
    content = raw_content(post)
    block, inline_url = leading_cover(content)
    media_id = int(post.get("featured_media") or 0)
    media = {}
    if media_id:
        embeds = (post.get("_embedded") or {}).get("wp:featuredmedia") or []
        media = next((item for item in embeds if item.get("id") == media_id), None)
        if not media or not media.get("source_url"):
            media = fetch_media(client, media_id)
    media_url = str(media.get("source_url") or "")
    featured_state = image_state(media_url, client, media.get("media_details"))
    matching_inline = (
        inline_url and wp_media_url(inline_url, client) and wp_media_url(media_url, client)
        and media_path(inline_url) == media_path(media_url)
    )
    inline_state = featured_state if matching_inline else (
        image_state(inline_url, client) if inline_url else "missing"
    )
    replace_featured = featured_state in {"striped", "previous_illustration", "missing", "invalid"}
    replace_inline = inline_state in {"striped", "previous_illustration", "missing", "invalid"}
    if not replace_featured and not replace_inline:
        return None
    if replace_featured and block and inline_state == "ok":
        inline_id = ATTACHMENT_CLASS.search(block.group())
        if inline_id:
            inline_media = fetch_media(client, int(inline_id.group(1)))
            if media_path(str(inline_media.get("source_url") or "")) == media_path(inline_url):
                return CoverRepair(inline_media, None, featured_state, inline_state)
    if not replace_featured and featured_state == "unknown":
        raise PublisherError("Impossibile verificare l'immagine in evidenza.")
    replace_span = block.span() if block and replace_inline else None
    return CoverRepair({} if replace_featured else media, replace_span, featured_state, inline_state)


def repair_post(client: WordPressClient, post: dict, upgrade: dict | None = None) -> dict | None:
    post_id = int(post["id"])
    title = raw_title(post)
    content = raw_content(post)
    credit = None
    filename = f"ai-vision-photo-{post_id}"
    if upgrade and post.get("featured_media") == upgrade["previous_media"]:
        block, inline_url = leading_cover(content)
        inline_id = ATTACHMENT_CLASS.search(block.group()) if block else None
        if block and not (
            (inline_id and int(inline_id.group(1)) == upgrade["previous_media"])
            or media_path(inline_url).endswith(f"/ai-vision-cover-{post_id}.png")
        ):
            raise PublisherError("Copertina interna modificata dopo la verifica.")
        plan = CoverRepair({}, block.span() if block else None, "previous_illustration", "previous_illustration")
        credit = CoverCredit(**upgrade["credit"])
    else:
        upgrade = None
        plan = plan_repair(client, post)
        if plan is None:
            return None
    media = plan.media
    url = client._url(f"posts/{post_id}")
    params = {"context": "edit", "_fields": "id,modified,status,featured_media,content,meta"}
    current = request_with_retry(client.session, "get", url, params=params).json()
    if (current.get("modified") != post.get("modified") or
            current.get("featured_media") != post.get("featured_media") or raw_content(current) != content):
        raise PublisherError("Articolo modificato durante il controllo, da riesaminare.")

    if not media:
        existing = request_with_retry(
            client.session, "get", client._url("media"),
            params={"slug": filename, "context": "edit", "_fields": "id,source_url,alt_text,mime_type"},
        ).json()
        media = next((item for item in existing if item.get("mime_type") == "image/jpeg"
                      and wp_media_url(item.get("source_url", ""), client)), None)
        credit = credit or CoverCredit("")
        if media is None:
            data = (UPGRADE_DIR / f"{post_id}.jpg").read_bytes() if upgrade else generate_ai_cover({"title": title})
            with Image.open(io.BytesIO(data)) as image:
                if image.format != "JPEG" or image.width < 960 or image.height < 540 or is_retired_cover(image):
                    raise PublisherError("Il file sostitutivo non è una copertina JPEG valida.")
                image.load()
            media = client.upload_media(data, filename + ".jpg", "image/jpeg", title, credit.markup())

    media_id = int(media["id"])
    if not wp_media_url(str(media.get("source_url") or ""), client):
        raise PublisherError("Copertina caricata senza un URL WordPress valido.")
    payload = {"featured_media": media_id}
    if plan.replace_span or not leading_cover(content)[0]:
        block = featured_image_block(media, str(media.get("alt_text") or title), credit)
        remaining = content[plan.replace_span[1]:] if plan.replace_span else content
        payload["content"] = block + remaining
        payload["meta"] = {"_jetpack_hide_featured_image": True}
    request_with_retry(client.session, "post", url, params={"context": "edit"}, json=payload)
    saved = request_with_retry(client.session, "get", url, params=params).json()
    if int(saved.get("featured_media") or 0) != media_id or raw_content(saved) != payload.get("content", content):
        raise PublisherError(f"Verifica WordPress fallita per articolo {post_id}.")
    return {
        "id": post_id, "title": title, "status": saved.get("status"), "link": post.get("link"),
        "featured_media": media_id, "source_url": media.get("source_url"),
        "previous_featured": plan.featured_state, "previous_inline": plan.inline_state,
    }


def main() -> int:
    if os.environ.get("WP_INLINE_IMAGE_REPAIR", "").strip().lower() != "true":
        print("Bloccato: impostare WP_INLINE_IMAGE_REPAIR=true per autorizzare le scritture.")
        return 2
    base_url = os.environ.get("WP_BASE_URL", "").strip()
    username = os.environ.get("WP_USERNAME", "").strip()
    app_password = os.environ.get("WP_APP_PASSWORD", "").strip()
    if not all((base_url, username, app_password)):
        print("Configurazione WordPress incompleta: WP_BASE_URL, WP_USERNAME e WP_APP_PASSWORD sono obbligatori.")
        return 2

    client = WordPressClient(base_url, username, app_password, dry_run=False)
    posts = fetch_all_posts(client)
    backup = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "site": base_url,
        "count": len(posts),
        "posts": posts,
    }
    write_json_atomic(BACKUP_PATH, backup)
    print(f"Backup integrale salvato prima delle modifiche: {BACKUP_PATH} ({len(posts)} articoli).")

    manifest = UPGRADE_DIR / "manifest.json"
    upgrades = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    repaired: list[dict] = []
    errors: list[dict] = []
    worker = local()

    def process(post):
        if not hasattr(worker, "client"):
            worker.client = WordPressClient(base_url, username, app_password, dry_run=False)
        return repair_post(worker.client, post, upgrades.get(str(post["id"])))

    with ThreadPoolExecutor(max_workers=5) as pool:
        pending = {pool.submit(process, post): post["id"] for post in posts}
        for future in as_completed(pending):
            post_id = pending[future]
            try:
                result = future.result()
                if result:
                    repaired.append(result)
                    print(f"OK #{post_id}: copertina {result['featured_media']} ({result['previous_featured']}/{result['previous_inline']}).")
            except Exception as exc:
                errors.append({"id": post_id, "error": f"{type(exc).__name__}: {exc}"})
                print(f"ERRORE #{post_id}: {type(exc).__name__}: {exc}")

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "site": base_url,
        "posts_scanned": len(posts),
        "repair_candidates": len(repaired) + len(errors),
        "repaired": len(repaired),
        "errors": errors,
        "items": repaired,
    }
    write_json_atomic(REPORT_PATH, report)
    print(f"Scansione: {len(posts)} articoli; riparati: {len(repaired)}; errori: {len(errors)}.")
    print(f"Report: {REPORT_PATH}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
