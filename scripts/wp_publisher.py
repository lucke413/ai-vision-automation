#!/usr/bin/env python3
"""Pubblica o pianifica gli articoli generati su WordPress.

Il modulo è volutamente separato dalla pipeline RSS/Gemini. In assenza di
``WP_DRY_RUN=false`` lavora in sola simulazione e non invia post a WordPress.

Gestisce:
- categorie macro di AI Vision;
- creazione/riuso dei tag;
- immagine dalla fonte o da OpenGraph;
- copertina grafica locale di riserva quando non c'è un'immagine scaricabile;
- cinque orari giornalieri configurabili in Europe/Rome;
- report JSON anche in caso di errori su singoli articoli.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import struct
import unicodedata
import zlib
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from requests.auth import HTTPBasicAuth


BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "article_drafts.json"
OUTPUT_FILE = BASE_DIR / "data" / "wp_publish_report.json"

VERSION = "1.0"
REQUEST_TIMEOUT = 30
MAX_IMAGE_BYTES = 10 * 1024 * 1024
USER_AGENT = "AI-Vision-WordPress-Publisher/1.0"

DEFAULT_TIMEZONE = "Europe/Rome"
DEFAULT_SLOT_TIMES = "08:00,10:30,14:00,16:30,20:30"

MACRO_CATEGORIES = (
    "News",
    "AI pratica",
    "Tool e Servizi",
    "Tecnologia e prodotti",
    "Sicurezza",
    "Guide",
    "Confronti",
    "Offerte",
)

SOURCE_CATEGORY_MAP = {
    "AI": "AI pratica",
    "Software & App": "Tool e Servizi",
    "Sicurezza": "Sicurezza",
    "Offerte & Prezzi": "Offerte",
    "Smartphone & Mobile": "Tecnologia e prodotti",
    "PC & Hardware": "Tecnologia e prodotti",
    "Gaming": "Tecnologia e prodotti",
    "Gadget & Consumer Tech": "Tecnologia e prodotti",
    "Streaming & Entertainment": "Tecnologia e prodotti",
    "Tecnologia": "Tecnologia e prodotti",
}

VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


class PublisherError(RuntimeError):
    """Errore che riguarda un singolo articolo o la configurazione."""


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:180] or "ai-vision-articolo"


def normalize_tag(value: Any) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text[:50]


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise PublisherError(f"File non trovato: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PublisherError(f"JSON non valido: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PublisherError(f"Formato JSON non valido: {path}")
    return data


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def get_timezone() -> ZoneInfo:
    name = os.environ.get("WP_TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise PublisherError(f"Fuso orario non valido: {name}") from exc


def parse_slot_times() -> list[dt_time]:
    raw = os.environ.get("WP_SLOT_TIMES", DEFAULT_SLOT_TIMES)
    result: list[dt_time] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            hour, minute = (int(part) for part in token.split(":", 1))
            value = dt_time(hour=hour, minute=minute)
        except (TypeError, ValueError) as exc:
            raise PublisherError(f"Orario WP non valido: {token}") from exc
        result.append(value)
    if not result:
        raise PublisherError("WP_SLOT_TIMES non contiene orari validi.")
    return sorted(set(result))


def next_publication_times(count: int, now: datetime | None = None) -> list[datetime]:
    if count <= 0:
        return []
    tz = get_timezone()
    current = (now or datetime.now(timezone.utc)).astimezone(tz)
    slots = parse_slot_times()
    result: list[datetime] = []
    day_offset = 0
    while len(result) < count and day_offset < 14:
        current_date = current.date() + timedelta(days=day_offset)
        for slot in slots:
            candidate = datetime.combine(current_date, slot, tzinfo=tz)
            if candidate <= current + timedelta(minutes=2):
                continue
            result.append(candidate)
            if len(result) == count:
                break
        day_offset += 1
    if len(result) != count:
        raise PublisherError("Impossibile costruire gli orari di pubblicazione.")
    return result


def category_for(draft: dict) -> str:
    category = str(draft.get("category") or "Tecnologia")
    story_type = str(draft.get("story_type") or "NEWS")
    title = str(draft.get("title") or "").lower()

    if story_type == "OFFERTA" or category == "Offerte & Prezzi":
        return "Offerte"
    if story_type == "GUIDA":
        return "Guide"
    if story_type == "SICUREZZA" or category == "Sicurezza":
        return "Sicurezza"
    if category == "AI":
        return "AI pratica"
    if story_type == "ANALISI" and re.search(r"\b(vs|contro|confronto|quale scegliere)\b", title):
        return "Confronti"
    if category in SOURCE_CATEGORY_MAP:
        return SOURCE_CATEGORY_MAP[category]
    if story_type == "NEWS":
        return "News"
    return "Tecnologia e prodotti"


def markdown_to_html(markdown_text: str) -> str:
    """Conversione minima sicura per i paragrafi prodotti dal generatore."""
    text = str(markdown_text or "").replace("\r\n", "\n").strip()
    if not text:
        return ""

    blocks = re.split(r"\n\s*\n", text)
    html_blocks: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        content = " ".join(lines)
        heading_match = re.match(r"^(#{2,3})\s+(.+)$", content)
        if heading_match:
            level = min(3, len(heading_match.group(1)))
            value = html.escape(heading_match.group(2).strip())
            html_blocks.append(f"<h{level}>{value}</h{level}>")
            continue
        if all(line.startswith(("- ", "* ")) for line in lines):
            entries = "".join(
                f"<li>{html.escape(line[2:].strip())}</li>" for line in lines
            )
            html_blocks.append(f"<ul>{entries}</ul>")
            continue
        escaped = html.escape(content)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
        html_blocks.append(f"<p>{escaped}</p>")
    return "\n".join(html_blocks)


def image_url_from_draft(draft: dict) -> str:
    for key in ("source_image_url", "image", "image_url"):
        value = str(draft.get(key) or "").strip()
        if value.startswith(("http://", "https://")):
            return value
    return ""


def extract_og_image(source_url: str, session: requests.Session) -> str:
    if not source_url:
        return ""
    try:
        response = session.get(
            source_url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return ""

    markup = response.text[:750_000]
    patterns = (
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, markup, flags=re.IGNORECASE)
        if match:
            candidate = html.unescape(match.group(1).strip())
            resolved = urljoin(source_url, candidate)
            if resolved.startswith(("http://", "https://")):
                return resolved
    return ""


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def fallback_png(category: str) -> bytes:
    """Crea una copertina grafica neutra senza dipendenze esterne."""
    width, height = 1200, 675
    digest = hashlib.sha256(category.encode("utf-8")).digest()
    base = (24 + digest[0] % 35, 36 + digest[1] % 35, 64 + digest[2] % 55)
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            diagonal = ((x + y) // 90) % 2 == 0
            band = (x // 160) % 3 == 0
            r, g, b = base
            if diagonal:
                r = min(255, r + 22)
                g = min(255, g + 14)
            if band and 90 < y < 585:
                b = min(255, b + 28)
            raw.extend((r, g, b))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) + png_chunk(
        b"IDAT", zlib.compress(bytes(raw), level=6)
    ) + png_chunk(b"IEND", b"")


def download_image(url: str, session: requests.Session) -> tuple[bytes, str] | None:
    if not url:
        return None
    try:
        response = session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None
    content = response.content
    if not content or len(content) > MAX_IMAGE_BYTES:
        return None
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix not in VALID_IMAGE_EXTENSIONS:
        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }.get(content_type, ".jpg")
    if content_type and not content_type.startswith("image/") and suffix not in VALID_IMAGE_EXTENSIONS:
        return None
    return content, suffix


class WordPressClient:
    def __init__(self, base_url: str, username: str, app_password: str, dry_run: bool):
        self.dry_run = dry_run
        self.base_url = base_url.rstrip("/")
        if self.base_url.endswith("/wp-json"):
            self.api_root = f"{self.base_url}/wp/v2"
        else:
            self.api_root = f"{self.base_url}/wp-json/wp/v2"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        if username or app_password:
            self.session.auth = HTTPBasicAuth(username, app_password)
        self.category_cache: dict[str, dict] = {}
        self.tag_cache: dict[str, dict] = {}

    def _url(self, resource: str) -> str:
        return f"{self.api_root}/{resource.lstrip('/')}"

    def get_or_create_term(self, kind: str, name: str) -> dict:
        cache = self.category_cache if kind == "categories" else self.tag_cache
        key = name.casefold()
        if key in cache:
            return cache[key]
        if self.dry_run:
            result = {"id": None, "name": name, "slug": slugify(name), "dry_run": True}
            cache[key] = result
            return result

        response = self.session.get(
            self._url(kind),
            params={"search": name, "per_page": 100},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        matches = response.json()
        for match in matches:
            if str(match.get("name", "")).casefold() == key:
                cache[key] = match
                return match

        response = self.session.post(
            self._url(kind),
            json={"name": name, "slug": slugify(name)},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 400:
            # Race condition or termine già esistente: rileggilo.
            response = self.session.get(
                self._url(kind),
                params={"search": name, "per_page": 100},
                timeout=REQUEST_TIMEOUT,
            )
        response.raise_for_status()
        result = response.json()
        cache[key] = result
        return result

    def existing_post(self, slug: str) -> dict | None:
        if self.dry_run:
            return None
        response = self.session.get(
            self._url("posts"),
            params={"slug": slug, "per_page": 1, "context": "edit"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        values = response.json()
        return values[0] if values else None

    def upload_media(self, content: bytes, filename: str, mime_type: str, alt_text: str, caption: str) -> dict:
        if self.dry_run:
            return {"id": None, "source_url": "dry-run", "alt_text": alt_text}
        response = self.session.post(
            self._url("media"),
            data=content,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": mime_type,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        media = response.json()
        media_id = media.get("id")
        if media_id:
            update = self.session.post(
                self._url(f"media/{media_id}"),
                json={"alt_text": alt_text, "caption": caption},
                timeout=REQUEST_TIMEOUT,
            )
            update.raise_for_status()
            media = update.json()
        return media

    def create_post(self, payload: dict) -> dict:
        if self.dry_run:
            return {"id": None, "link": "dry-run", "status": "planned", "payload": payload}
        response = self.session.post(
            self._url("posts"),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()


def image_mime(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix.lower(), "image/png")


def draft_items(data: dict) -> list[dict]:
    values = data.get("daily_items")
    if not isinstance(values, list):
        values = [item for item in data.get("items", []) if item.get("publication_slot") == "today"]
    return [item for item in values if isinstance(item, dict)]


def publish_one(
    draft: dict,
    planned_time: datetime,
    client: WordPressClient,
    session: requests.Session,
) -> dict:
    title = str(draft.get("title") or "").strip()
    if not title:
        raise PublisherError("Titolo mancante.")
    body = markdown_to_html(str(draft.get("body_markdown") or ""))
    if not body:
        raise PublisherError("Corpo articolo vuoto.")

    category_name = category_for(draft)
    category = client.get_or_create_term("categories", category_name)
    raw_tags = draft.get("tags") if isinstance(draft.get("tags"), list) else []
    tags = []
    seen_tags: set[str] = set()
    for raw_tag in raw_tags:
        tag = normalize_tag(raw_tag)
        if not tag or tag.casefold() in seen_tags:
            continue
        seen_tags.add(tag.casefold())
        tags.append(client.get_or_create_term("tags", tag))

    source_url = str(draft.get("source_url") or "").strip()
    source = str(draft.get("source") or "Fonte originale").strip()
    if source_url.startswith(("http://", "https://")):
        body += (
            f'\n<p><small>Fonte: <a href="{html.escape(source_url, quote=True)}" '
            f'rel="nofollow noopener" target="_blank">{html.escape(source)}</a></small></p>'
        )

    image_url = image_url_from_draft(draft)
    if client.dry_run:
        # Il dry-run non deve fare richieste esterne né scaricare immagini:
        # usa una copertina simulata e registra se una fonte era disponibile.
        image_origin = "dry_run_source" if image_url else "dry_run_fallback"
        downloaded = (fallback_png(category_name), ".png")
    else:
        image_origin = "rss_or_draft"
        downloaded = download_image(image_url, session) if image_url else None
        if downloaded is None and source_url:
            image_url = extract_og_image(source_url, session)
            image_origin = "open_graph"
            downloaded = download_image(image_url, session) if image_url else None
        if downloaded is None:
            downloaded = (fallback_png(category_name), ".png")
            image_origin = "generated_fallback"
    image_bytes, suffix = downloaded
    filename = f"{slugify(title)}{suffix}"
    media = client.upload_media(
        image_bytes,
        filename,
        image_mime(suffix),
        alt_text=title,
        caption=f"Immagine associata a: {title}",
    )

    slug = slugify(str(draft.get("slug") or title))
    existing = client.existing_post(slug)
    if existing:
        return {
            "article_id": draft.get("article_id"),
            "title": title,
            "status": "already_exists",
            "post_id": existing.get("id"),
            "link": existing.get("link"),
            "category": category_name,
            "image_origin": image_origin,
        }

    local_date = planned_time.strftime("%Y-%m-%dT%H:%M:%S")
    utc_date = planned_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    payload = {
        "title": title,
        "content": body,
        "excerpt": str(draft.get("excerpt") or ""),
        "slug": slug,
        "status": "future",
        "date": local_date,
        "date_gmt": utc_date,
        "categories": [category["id"]] if category.get("id") else [],
        "tags": [tag["id"] for tag in tags if tag.get("id")],
        "featured_media": media.get("id") or 0,
    }
    created = client.create_post(payload)
    return {
        "article_id": draft.get("article_id"),
        "title": title,
        "status": "planned" if client.dry_run else "published",
        "post_id": created.get("id"),
        "link": created.get("link"),
        "scheduled_local": local_date,
        "scheduled_utc": utc_date,
        "category": category_name,
        "tags": [tag.get("name") for tag in tags],
        "image_origin": image_origin,
        "image_source_url": image_url or None,
        "media_id": media.get("id"),
    }


def main() -> int:
    data = load_json(INPUT_FILE)
    drafts = draft_items(data)
    dry_run = env_bool("WP_DRY_RUN", True)
    base_url = os.environ.get("WP_BASE_URL", "").strip().rstrip("/")
    username = os.environ.get("WP_USERNAME", "").strip()
    app_password = os.environ.get("WP_APP_PASSWORD", "").strip()
    if not dry_run and (not base_url or not username or not app_password):
        raise PublisherError(
            "Per la pubblicazione reale servono WP_BASE_URL, WP_USERNAME e WP_APP_PASSWORD."
        )
    if not drafts:
        output = {
            "publisher_version": VERSION,
            "status": "empty",
            "dry_run": dry_run,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "requested": 0,
            "completed": 0,
            "errors": [],
            "items": [],
        }
        save_json(OUTPUT_FILE, output)
        print("WP PUBLISHER: nessun articolo giornaliero da pubblicare.")
        return 0

    client = WordPressClient(base_url, username, app_password, dry_run)
    schedule = next_publication_times(len(drafts))
    results: list[dict] = []
    errors: list[dict] = []
    used_slugs: set[str] = set()
    for draft, planned_time in zip(drafts, schedule):
        try:
            slug = slugify(str(draft.get("slug") or draft.get("title") or ""))
            if slug in used_slugs:
                raise PublisherError("Slug duplicato nello stesso lotto.")
            used_slugs.add(slug)
            results.append(publish_one(draft, planned_time, client, client.session))
            print(f"OK: {draft.get('title', '')} -> {planned_time.isoformat()}")
        except Exception as exc:
            error = {
                "article_id": draft.get("article_id"),
                "title": draft.get("title"),
                "error": f"{type(exc).__name__}: {exc}",
            }
            errors.append(error)
            print(f"AVVISO: articolo non pubblicato: {error['title']} — {error['error']}")

    output = {
        "publisher_version": VERSION,
        "status": "dry_run" if dry_run and not errors else ("ok" if not errors else "ok_with_warnings"),
        "dry_run": dry_run,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": os.environ.get("WP_TIMEZONE", DEFAULT_TIMEZONE),
        "slot_times": [value.strftime("%H:%M") for value in parse_slot_times()],
        "requested": len(drafts),
        "completed": len(results),
        "errors": errors,
        "items": results,
    }
    save_json(OUTPUT_FILE, output)
    print(f"WP PUBLISHER: {len(results)}/{len(drafts)} articoli elaborati.")
    print(f"Report: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PublisherError as exc:
        print(f"ERRORE: {exc}")
        raise SystemExit(1)
