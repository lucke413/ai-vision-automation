#!/usr/bin/env python3
"""Crea/aggiorna una pagina WordPress con gli ultimi articoli per il link in bio Instagram."""

from __future__ import annotations

import base64
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "AI-Vision-Instagram-Hub/1.0"
SLUG = "instagram"
TITLE = "AI Vision - articoli da Instagram"
LIMIT = 12


def request_json(url: str, method: str = "GET", payload: dict | None = None, auth: tuple[str, str] | None = None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if auth:
        raw = f"{auth[0]}:{auth[1]}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"WordPress HTTP {exc.code}: {detail}") from None


def plain(value: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(text).split())


def build_content(posts: list[dict]) -> str:
    parts = [
        "<p>Hai visto un articolo su Instagram? Qui trovi gli ultimi contenuti pubblicati da AI Vision.</p>",
        "<hr>",
    ]
    for post in posts:
        title = html.escape(plain(post.get("title", {}).get("rendered", "")))
        link = html.escape(str(post.get("link") or ""), quote=True)
        excerpt = html.escape(plain(post.get("excerpt", {}).get("rendered", "")))
        if not title or not link:
            continue
        parts.append(f'<h2><a href="{link}">{title}</a></h2>')
        if excerpt:
            parts.append(f"<p>{excerpt}</p>")
        parts.append(f'<p><a href="{link}"><strong>Leggi l\'articolo completo →</strong></a></p>')
        parts.append("<hr>")
    return "\n".join(parts)


def main() -> int:
    base = os.environ.get("WP_BASE_URL", "").strip().rstrip("/")
    user = os.environ.get("WP_USERNAME", "").strip()
    password = os.environ.get("WP_APP_PASSWORD", "").strip()
    if not base or not user or not password:
        raise RuntimeError("Servono WP_BASE_URL, WP_USERNAME e WP_APP_PASSWORD.")
    api = f"{base}/wp-json/wp/v2"
    auth = (user, password)

    query = urllib.parse.urlencode({
        "status": "publish",
        "per_page": LIMIT,
        "orderby": "date",
        "order": "desc",
        "_fields": "id,title,excerpt,link,date",
    })
    posts = request_json(f"{api}/posts?{query}")
    if not isinstance(posts, list):
        raise RuntimeError("Risposta articoli WordPress non valida.")

    existing_q = urllib.parse.urlencode({"slug": SLUG, "status": "any", "per_page": 1, "context": "edit"})
    pages = request_json(f"{api}/pages?{existing_q}", auth=auth)
    payload = {
        "title": TITLE,
        "slug": SLUG,
        "status": "publish",
        "content": build_content(posts),
    }

    if isinstance(pages, list) and pages:
        page_id = pages[0]["id"]
        result = request_json(f"{api}/pages/{page_id}", method="POST", payload=payload, auth=auth)
        action = "aggiornata"
    else:
        result = request_json(f"{api}/pages", method="POST", payload=payload, auth=auth)
        action = "creata"

    link = str(result.get("link") or f"{base}/{SLUG}/")
    print(f"Pagina Instagram {action}: {link}")
    print(f"Articoli mostrati: {len(posts)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        raise SystemExit(1)
