#!/usr/bin/env python3
"""Audit e pulizia dei link redazionali nei post pubblicati e programmati."""
from __future__ import annotations

import collections
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

import seo_archive_recovery as recovery
from inline_image_repair import request_with_retry
from public_source_links import clean_source_links, marked_source_url
from source_originality_audit import audit_originality, recorded_checks

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "public_source_cleanup.json"
BACKUP = Path(__file__).resolve().parents[1] / "data" / "public_source_cleanup_backups.json"
PLAN = Path(__file__).resolve().parents[1] / "data" / "source_cleanup_plan.json"
API = recovery.BASE_URL + "/wp-json/wp/v2/posts"
FIELDS = "id,status,date,date_gmt,modified,slug,title,content,featured_media"
TIMEOUT = (5, 20)
UA = "AIVision-Public-Source-Cleanup/1.0"
def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def wp_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = UA
    base = os.environ.get("WP_BASE_URL", "").strip().rstrip("/").removesuffix("/wp-json")
    username = os.environ.get("WP_USERNAME", "").strip()
    password = os.environ.get("WP_APP_PASSWORD", "").strip()
    if base and base != recovery.BASE_URL:
        raise ValueError("WP_BASE_URL non corrisponde al dominio autorizzato.")
    if username or password:
        if not username or not password or base != recovery.BASE_URL:
            raise ValueError("Configurazione credenziali WordPress incompleta o non valida.")
        session.auth = HTTPBasicAuth(username, password)
    return session


def read_posts(session: requests.Session) -> list[dict]:
    posts = {}
    for status in ("publish", "future") if session.auth else ("publish",):
        page = 1
        while True:
            response = request_with_retry(session, "get", API, params={
                "status": status, "context": "edit" if session.auth else "view", "page": page,
                "per_page": 50, "orderby": "id", "order": "asc", "_fields": FIELDS,
            })
            batch = response.json()
            pages = response.headers.get("X-WP-TotalPages")
            if not isinstance(batch, list) or any(not isinstance(post, dict) for post in batch):
                raise RuntimeError(f"Inventario WordPress non valido per {status}, pagina {page}.")
            field = "raw" if session.auth else "rendered"
            for post in batch:
                if post.get("status") != status or not isinstance((post.get("content") or {}).get(field), str):
                    raise RuntimeError(f"Inventario WordPress incompleto per articolo {post.get('id')}.")
                posts[post["id"]] = post
            if (pages and page >= int(pages)) or (not pages and len(batch) < 50):
                break
            page += 1
            if page > 100:
                raise RuntimeError("Troppe pagine nell'inventario WordPress.")
    return list(posts.values())


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def prepare(session: requests.Session) -> int:
    posts = read_posts(session)
    records, unreadable = recorded_checks()
    field = "raw" if session.auth else "rendered"
    changes = []
    for post in posts:
        before = post["content"][field]
        record = records.setdefault(post["id"], {})
        if not record.get("source_url"):
            source = marked_source_url(before)
            if source:
                record["source_url"] = source
        source = record.get("source_url") or ""
        after, links = clean_source_links(before, source)
        if after != before:
            changes.append({"id": post["id"], "status": post["status"], "modified": post["modified"],
                            "before": before, "after": after, "links": links})
    count = collections.Counter(post["status"] for post in posts)
    print(f"Inventario: {count['publish']} pubblicati, {count['future']} programmati. "
          f"Articoli con riferimenti da rimuovere: {len(changes)}.")
    # Full raw text of scheduled articles stays in the runner and WordPress.
    backups = [
        {"post_id": row["id"], "status": row["status"], "modified": row["modified"],
         "before_sha256": content_hash(row["before"]), "after_sha256": content_hash(row["after"]),
         **({"content_before": row["before"]} if row["status"] == "publish" else {})}
        for row in changes
    ]
    write_json(BACKUP, {"site": recovery.BASE_URL, "posts": backups})
    write_json(PLAN, {"inventory": dict(count), "changes": changes,
                      "records": records, "unreadable_workflow_reports": unreadable})
    return 0


def apply_one(row: dict) -> dict:
    session = wp_session()
    endpoint = f"{API}/{row['id']}"
    params = {"context": "edit", "_fields": FIELDS}
    current = request_with_retry(session, "get", endpoint, params=params).json()
    base = {"id": row["id"], "status_wp": current.get("status"), "links": row["links"]}
    if (current.get("content") or {}).get("raw") == row["after"]:
        return {**base, "status": "already_clean"}
    if (current.get("modified") != row["modified"]
            or (current.get("content") or {}).get("raw") != row["before"]
            or current.get("status") not in {"publish", "future"}):
        return {**base, "status": "changed_since_audit"}
    request_with_retry(session, "post", endpoint, params=params, json={"content": row["after"]},
                       allow_redirects=False)
    saved = request_with_retry(session, "get", endpoint, params=params).json()
    if ((saved.get("content") or {}).get("raw") != row["after"]
            or any(saved.get(key) != current.get(key) for key in ("id", "status", "date", "date_gmt", "slug", "featured_media", "title"))):
        raise RuntimeError("Esito WordPress da verificare.")
    return {**base, "status": "removed_and_verified"}


def apply(session: requests.Session) -> int:
    if not session.auth:
        raise PermissionError("Credenziali WordPress necessarie per gli articoli programmati.")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    records = {int(key): value for key, value in plan["records"].items()}
    removed = []
    errors = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        tasks = {pool.submit(apply_one, row): row["id"] for row in plan["changes"]}
        for task in as_completed(tasks):
            try:
                removed.append(task.result())
            except Exception as exc:
                errors.append({"id": tasks[task], "error": f"{type(exc).__name__}: {exc}"})

    posts = read_posts(session)
    remaining = [
        post["id"] for post in posts
        if clean_source_links(post["content"]["raw"], records.get(post["id"], {}).get("source_url") or "")[1]
    ]
    verified = collections.Counter(row["status_wp"] for row in removed if row["status"] == "removed_and_verified")
    output = {"inventory": plan["inventory"], "current_inventory": dict(collections.Counter(p["status"] for p in posts)),
              "removed": dict(verified), "remaining": remaining, "errors": errors, "results": removed,
              "unreadable_workflow_reports": plan["unreadable_workflow_reports"]}
    write_json(OUTPUT, output)
    print(f"Rimossi e verificati: {verified['publish']} pubblicati, {verified['future']} programmati. "
          f"Da controllare: {len(remaining)}. Errori: {len(errors)}.")
    by_status, live = audit_originality(posts, records)
    output.update(originality_records=by_status, originality_rechecks=live)
    write_json(OUTPUT, output)
    print("Originalità registrata: " + json.dumps(by_status, ensure_ascii=False))
    for state in ("publish", "future"):
        sampled = collections.Counter(row["check"] for row in live if row["status_wp"] == state)
        print(f"Confronto attuale {state}: {dict(sampled)}")
    return 1 if errors or remaining else 0


def main() -> int:
    import sys
    session = wp_session()
    if sys.argv[1:] == ["--apply"]:
        return apply(session)
    prepare(session)
    if os.environ.get("SEO_PUBLIC_CLEANUP_ALLOW_WRITES") == "YES":
        return apply(session)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    write_json(OUTPUT, {"mode": "dry_run", "inventory": plan["inventory"],
                        "source_footers_found": len(plan["changes"])})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
