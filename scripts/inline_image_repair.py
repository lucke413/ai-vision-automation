#!/usr/bin/env python3
"""Ripara le copertine mancanti nel corpo degli articoli WordPress.

Il programma è fail-closed: richiede WP_INLINE_IMAGE_REPAIR=true, salva prima
un backup integrale di tutti i post publish/future e poi modifica soltanto i
post con featured_media valido ma senza immagini nel contenuto.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.wp_publisher import PublisherError, WordPressClient, featured_image_block
except ModuleNotFoundError:  # esecuzione diretta: python scripts/inline_image_repair.py
    from wp_publisher import PublisherError, WordPressClient, featured_image_block

ROOT = Path(__file__).resolve().parent.parent
BACKUP_PATH = ROOT / "data" / "inline_image_repair_backup.json"
REPORT_PATH = ROOT / "data" / "inline_image_repair_report.json"
PER_PAGE = 100


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def request_with_retry(session, method: str, url: str, **kwargs):
    last_error = None
    for attempt in range(1, 5):
        try:
            response = getattr(session, method)(url, timeout=45, **kwargs)
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except Exception as exc:
            last_error = exc
        if attempt < 4:
            time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(f"Richiesta WordPress fallita dopo 4 tentativi: {url}") from last_error


def raw_content(post: dict) -> str:
    value = post.get("content")
    if isinstance(value, dict):
        return str(value.get("raw") or value.get("rendered") or "")
    return str(value or "")


def has_leading_cover(content: str) -> bool:
    value = str(content or "").lstrip()
    if re.match(r"<!--\s*wp:image\b", value, flags=re.IGNORECASE):
        end = value.lower().find("<!-- /wp:image -->")
        first_block = value[:end] if end >= 0 else value[:2500]
        return bool(re.search(r"<img\b", first_block, flags=re.IGNORECASE))
    if re.match(r"<figure\b", value, flags=re.IGNORECASE):
        match = re.match(r"<figure\b.*?</figure>", value, flags=re.IGNORECASE | re.DOTALL)
        return bool(match and re.search(r"<img\b", match.group(0), flags=re.IGNORECASE))
    return bool(re.match(r"<img\b", value, flags=re.IGNORECASE))

def needs_inline_cover(post: dict) -> bool:
    content = raw_content(post)
    if not post.get("featured_media"):
        return False
    if not has_leading_cover(content):
        return True
    # Anche una copertina già presente in cima deve essere priva del bordo blu.
    return "border-style:none;border-width:0px" not in content[:2500]


def normalize_leading_cover(content: str) -> str:
    value = str(content or "")
    if not has_leading_cover(value):
        return value
    stripped = value.lstrip()
    if stripped.startswith("<!-- wp:image"):
        match = re.match(r"(<!--\s*wp:image\s+)(\{.*?\})(\s*-->)", stripped, flags=re.DOTALL)
        if match:
            attrs = json.loads(match.group(2))
            style = attrs.setdefault("style", {})
            border = style.setdefault("border", {})
            border["width"] = "0px"
            border["style"] = "none"
            comment = match.group(1) + json.dumps(attrs, ensure_ascii=False, separators=(",", ":")) + match.group(3)
            value = value.replace(match.group(0), comment, 1)
        value = re.sub(
            r'(<figure\b[^>]*class="[^"]*)(")',
            lambda m: m.group(1) + (" has-custom-border" if "has-custom-border" not in m.group(1) else "") + m.group(2),
            value,
            count=1,
            flags=re.IGNORECASE,
        )
    def style_first_image(match):
        tag = match.group(0)
        if re.search(r'\bstyle\s*=', tag, flags=re.IGNORECASE):
            return re.sub(
                r'\bstyle=(["\'])(.*?)\1',
                lambda m: 'style=' + m.group(1) + m.group(2).rstrip(";") + ';border-style:none;border-width:0px' + m.group(1),
                tag,
                count=1,
                flags=re.IGNORECASE,
            )
        return tag[:-1] + ' style="border-style:none;border-width:0px">'
    return re.sub(r"<img\b[^>]*>", style_first_image, value, count=1, flags=re.IGNORECASE)


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
                    "_fields": "id,title,status,date,modified,featured_media,content,meta,link",
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

def fetch_media(client: WordPressClient, media_id: int, cache: dict) -> dict:
    if media_id in cache:
        return cache[media_id]
    response = request_with_retry(
        client.session,
        "get",
        client._url(f"media/{media_id}"),
        params={"context": "edit", "_fields": "id,source_url,alt_text,mime_type"},
    )
    media = response.json()
    if not isinstance(media, dict) or not str(media.get("mime_type") or "").startswith("image/"):
        raise PublisherError(f"Allegato {media_id} non è un'immagine valida.")
    cache[media_id] = media
    return media


def repair_post(client: WordPressClient, post: dict, media_cache: dict) -> dict:
    post_id = int(post["id"])
    media_id = int(post["featured_media"])
    title_value = post.get("title")
    title = str(title_value.get("raw") or title_value.get("rendered") or "") if isinstance(title_value, dict) else str(title_value or "")
    media = fetch_media(client, media_id, media_cache)
    existing_content = raw_content(post)
    if has_leading_cover(existing_content):
        updated_content = normalize_leading_cover(existing_content)
    else:
        updated_content = featured_image_block(media, title) + existing_content
    request_with_retry(
        client.session,
        "post",
        client._url(f"posts/{post_id}"),
        params={"context": "edit"},
        json={
            "content": updated_content,
            "meta": {"_jetpack_hide_featured_image": True},
        },
    )
    verify = request_with_retry(
        client.session,
        "get",
        client._url(f"posts/{post_id}"),
        params={"context": "edit", "_fields": "id,status,featured_media,content,meta"},
    ).json()
    saved_content = raw_content(verify)
    if "<img" not in saved_content.lower() or int(verify.get("featured_media") or 0) != media_id:
        raise RuntimeError(f"Verifica fallita per articolo {post_id}.")
    return {
        "id": post_id,
        "title": title,
        "status": verify.get("status"),
        "featured_media": media_id,
        "image_in_content": True,
        "hide_featured_image": (verify.get("meta") or {}).get("_jetpack_hide_featured_image"),
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

    targets = [post for post in posts if needs_inline_cover(post)]
    media_cache: dict[int, dict] = {}
    repaired: list[dict] = []
    errors: list[dict] = []
    skipped: list[dict] = []
    for index, post in enumerate(targets, start=1):
        post_id = post.get("id")
        if not post.get("featured_media"):
            skipped.append({"id": post_id, "reason": "featured_media assente"})
            continue
        try:
            result = repair_post(client, post, media_cache)
            repaired.append(result)
            print(f"[{index}/{len(targets)}] OK #{post_id}: immagine inserita nel contenuto.")
        except Exception as exc:
            errors.append({"id": post_id, "error": f"{type(exc).__name__}: {exc}"})
            print(f"[{index}/{len(targets)}] ERRORE #{post_id}: {type(exc).__name__}: {exc}")

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "site": base_url,
        "posts_scanned": len(posts),
        "repair_candidates": len(targets),
        "repaired": len(repaired),
        "errors": errors,
        "skipped": skipped,
        "items": repaired,
    }
    write_json_atomic(REPORT_PATH, report)
    print(f"Scansione: {len(posts)} articoli; riparati: {len(repaired)}; errori: {len(errors)}.")
    print(f"Report: {REPORT_PATH}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
