#!/usr/bin/env python3
"""Audit e pulizia reversibile dei footer bibliografici dagli articoli AIVision.

Default: sola lettura. La modalità di scrittura rimuove esclusivamente
l'ultimo paragrafo se è una riga autonoma "Fonte: <link>" / "Bibliografia: <link>".
Non modifica testo editoriale, titolo, slug, date, stato, immagini o SEO.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth

import seo_archive_recovery as recovery

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "public_source_cleanup.json"
BACKUP = Path(__file__).resolve().parents[1] / "data" / "public_source_cleanup_backups.json"
TIMEOUT = (5, 20)
UA = "AIVision-Public-Source-Cleanup/1.0"
FOOTER_LABEL = re.compile(
    r"^(?:fonte(?:\s+di\s+riferimento)?|fonti(?:\s+di\s+riferimento)?|"
    r"riferimenti|bibliografia)\s*:\s*.+$",
    re.IGNORECASE,
)


def last_source_footer(content: str) -> str:
    """Restituisce l'ultimo paragrafo solo se è una bibliografia linkata autonoma."""
    value = str(content or "")
    blocks = list(re.finditer(
        r"(?:<!--\s*wp:paragraph(?:\s+[^>]*)?-->\s*)?<p\b[^>]*>.*?</p\s*>(?:\s*<!--\s*/wp:paragraph\s*-->)?",
        value, re.IGNORECASE | re.DOTALL,
    ))
    if not blocks:
        return ""
    match = blocks[-1]
    if value[match.end():].strip():
        return ""
    block = match.group(0)
    if not re.search(r"<a\b[^>]*href\s*=", block, re.IGNORECASE):
        return ""
    visible = html.unescape(re.sub(r"<[^>]+>", " ", block))
    visible = re.sub(r"\s+", " ", visible).strip()
    if len(visible) > 240 or not FOOTER_LABEL.fullmatch(visible):
        return ""
    return block


def remove_last_source_footer(content: str) -> tuple[str, str]:
    value = str(content or "")
    block = last_source_footer(value)
    if not block:
        return value, ""
    position = value.rfind(block)
    if position < 0:
        return value, ""
    cleaned = (value[:position] + value[position + len(block):]).rstrip()
    return cleaned, block


def save_backup(rows: list[dict]) -> None:
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    temp = BACKUP.with_suffix(".tmp")
    temp.write_text(json.dumps({
        "site": recovery.BASE_URL,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "only final standalone linked source paragraph",
        "posts": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(BACKUP)


def wp_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = UA
    base = os.environ.get("WP_BASE_URL", "").strip().rstrip("/")
    if base.endswith("/wp-json"):
        base = base[:-len("/wp-json")]
    username = os.environ.get("WP_USERNAME", "").strip()
    password = os.environ.get("WP_APP_PASSWORD", "").strip()
    if base and base != recovery.BASE_URL:
        raise ValueError("WP_BASE_URL non corrisponde al dominio autorizzato.")
    if username or password:
        if not username or not password or base != recovery.BASE_URL:
            raise ValueError("Configurazione credenziali WordPress incompleta o non valida.")
        session.auth = HTTPBasicAuth(username, password)
    return session


def read_edit_post(session: requests.Session, post_id: int) -> dict:
    endpoint = urljoin(recovery.BASE_URL + "/", f"wp-json/wp/v2/posts/{post_id}")
    response = recovery.get(session, endpoint, params={"context": "edit"})
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise ValueError("Risposta WordPress non valida.")
    return value


def main() -> int:
    apply = os.environ.get("SEO_PUBLIC_CLEANUP_ALLOW_WRITES") == "YES"
    session = wp_session()
    posts, inventory = recovery.archive(session)
    if not inventory.get("complete"):
        raise RuntimeError("Inventario WordPress incompleto: nessuna modifica consentita.")

    candidates = []
    for post in posts:
        rendered = (post.get("content") or {}).get("rendered") or ""
        footer = last_source_footer(rendered)
        if footer:
            title = recovery.plain((post.get("title") or {}).get("rendered") or "")
            candidates.append({
                "id": int(post["id"]),
                "url": str(post.get("link") or ""),
                "slug": str(post.get("slug") or ""),
                "modified": str(post.get("modified") or ""),
                "title": title,
                "detected_footer": recovery.plain(footer),
                "status": "candidate_readonly",
            })

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "site": recovery.BASE_URL,
        "mode": "apply" if apply else "dry_run",
        "inventory": inventory,
        "source_footers_found": len(candidates),
        "source_footers_removed": 0,
        "posts": candidates,
        "errors": [],
    }
    backups: list[dict] = []
    if apply:
        if not session.auth:
            raise PermissionError("Per scrivere servono credenziali WordPress nei secrets GitHub.")
        if not candidates:
            report["note"] = "Nessun footer bibliografico finale rilevato."
        for row in candidates:
            try:
                current = read_edit_post(session, row["id"])
                current_title = recovery.plain((current.get("title") or {}).get("rendered") or "")
                raw = (current.get("content") or {}).get("raw")
                if (
                    current.get("status") != "publish"
                    or current.get("link") != row["url"]
                    or current.get("slug") != row["slug"]
                    or current.get("modified") != row["modified"]
                    or current_title != row["title"]
                    or not isinstance(raw, str)
                ):
                    row["status"] = "skipped_post_changed_or_raw_unavailable"
                    continue
                cleaned, footer = remove_last_source_footer(raw)
                if not footer:
                    row["status"] = "skipped_footer_not_exact_in_edit_content"
                    continue
                backup = {
                    "post_id": row["id"],
                    "url": row["url"],
                    "slug": row["slug"],
                    "modified_before": row["modified"],
                    "title": row["title"],
                    "content_before": raw,
                    "removed_footer": footer,
                }
                backups.append(backup)
                save_backup(backups)
                endpoint = urljoin(recovery.BASE_URL + "/", f"wp-json/wp/v2/posts/{row['id']}")
                response = session.post(
                    endpoint,
                    params={"context": "edit"},
                    json={"content": cleaned},
                    timeout=TIMEOUT,
                    allow_redirects=False,
                )
                response.raise_for_status()
                saved = response.json()
                saved_raw = (saved.get("content") or {}).get("raw")
                if saved_raw != cleaned:
                    row["status"] = "write_unconfirmed_check_wordpress"
                    continue
                row["status"] = "removed_and_verified"
                report["source_footers_removed"] += 1
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                row["status"] = "error"
                report["errors"].append({
                    "post_id": row["id"],
                    "error": f"{type(exc).__name__}: {str(exc)[:180]}",
                })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"SOURCE FOOTER AUDIT: {inventory['retrieved']} articoli; "
        f"{len(candidates)} footer autonomi rilevati; "
        f"{report['source_footers_removed']} rimossi e verificati; "
        f"errori: {len(report['errors'])}; mode={report['mode']}."
    )
    for row in candidates:
        print(f"  [{row['id']}] {row['status']} | {row['title']} | {row['detected_footer']}")
    print(f"Report: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
