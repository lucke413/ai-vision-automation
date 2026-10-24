#!/usr/bin/env python3
"""Recupero SEO archivio AIVision: analisi completa e metadati verificati.

Default: SOLA LETTURA, nessuna variazione agli articoli.
La modalità --apply-meta può compilare SOLO meta description già assenti,
sfruttando testo presente nell'articolo, senza inventare informazioni.
Niente allungamenti a un conteggio artificiale, link affiliati, redirect,
cambi di slug/status/data/titolo, modifiche al corpo o rimozioni.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import datetime as dt
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urljoin

import requests
from requests.auth import HTTPBasicAuth

from seo_site_audit import BASE_URL, PageMeta, analyze_post, plain

OUTPUT_FILE = Path(__file__).resolve().parents[1] / "data" / "seo_archive_recovery.json"
MAX_ARCHIVE = 1000
MAX_SHORT = 300
MAX_APPLY = 6
MAX_META_SCAN_WORKERS = 4
BACKUP_FILE = Path(__file__).resolve().parents[1] / "data" / "seo_archive_backups.json"
TIMEOUT = (5, 15)
UA = "AIVision-SEO-Archive-Recovery/1.0 (manual read-only by default)"
STOPWORDS = {
    "della", "delle", "degli", "dallo", "dalle", "questo", "questa",
    "nuovo", "nuova", "arriva", "arrivano", "offerta", "sconto",
    "prezzo", "amazon", "come", "dopo", "prima", "disponibile",
    "tutti", "delle", "ecco", "prezzi", "sulla", "nella", "degli",
}
EXPIRED_OFFER = re.compile(
    r"\b(?:offert[ae]|scont[oi]|coupon|promo|codice promozionale|"
    r"minimo storico|prime day|percentuale di sconto)\b", re.I
)
SENSITIVE = re.compile(r"\b(?:vulnerabilit[aà]|zero.day|sicurezza|attacch[io])\b", re.I)
FIRST_HAND = re.compile(r"\b(?:recensione|prova su strada|test del|in prova)\b", re.I)
INSTANT_PROMO = re.compile(
    r"\b(?:acquista subito|scade oggi|solo oggi|ultime ore|approfitta|"
    r"disponibile ora|prezzo minimo|coupon|in offerta|sconto)\b", re.I
)
INTERNAL_NOTES = re.compile(
    r"\b(?:prima della pubblicazione|fact.check|da verificare|"
    r"stando alla fonte|secondo la fonte|la bozza)\b", re.I
)


def site_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and parsed.hostname == urlsplit(BASE_URL).hostname
            and parsed.port in (None, 443)
            and parsed.username is None and parsed.password is None
        )
    except ValueError:
        return False


def get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    if not site_url(url):
        raise ValueError("L'URL non appartiene al sito autorizzato")
    response = session.get(url, timeout=TIMEOUT, allow_redirects=False, **kwargs)
    # Non seguire redirect automatici verso terze parti.
    if 300 <= response.status_code < 400:
        raise ValueError(f"Redirect non seguito: HTTP {response.status_code}")
    return response


def archive(session: requests.Session) -> tuple[list[dict], dict]:
    posts: list[dict] = []
    info = {"total_header": None, "pages": 0, "complete": False, "errors": []}
    api = urljoin(BASE_URL + "/", "wp-json/wp/v2/posts")
    for page in range(1, 1 + MAX_ARCHIVE // 100):
        try:
            response = get(session, api, params={
                "status": "publish", "per_page": 100, "page": page,
                "_fields": "id,title,content,excerpt,link,slug,date,modified,featured_media",
            })
            response.raise_for_status()
            values = response.json()
            if not isinstance(values, list):
                raise ValueError("La risposta REST non contiene gli articoli")
            total = response.headers.get("X-WP-Total")
            if total and total.isdigit():
                info["total_header"] = int(total)
            posts.extend(values)
            info["pages"] += 1
            if len(values) < 100 or len(posts) >= MAX_ARCHIVE:
                break
        except (requests.RequestException, ValueError, TypeError) as exc:
            info["errors"].append(f"Pagina {page}: {type(exc).__name__}: {str(exc)[:150]}")
            break
    info["retrieved"] = len(posts)
    info["complete"] = (
        not info["errors"]
        and info["total_header"] is not None
        and len(posts) == info["total_header"]
    )
    return posts, info


def topic_tokens(text: str) -> set[str]:
    return {
        term for term in re.findall(r"[a-zà-ù0-9]{3,}", plain(text).lower())
        if term not in STOPWORDS
    }


def reason_for_article(title: str) -> tuple[str, str]:
    if EXPIRED_OFFER.search(title):
        return ("offerta_da_ricontrollare",
                "Verificare attualità del prezzo; non ampliare promozioni scadute.")
    if FIRST_HAND.search(title):
        return ("esperienza_o_recensione_da_attribuire",
                "Verificare che test e giudizi siano attribuiti a chi li ha svolti.")
    if SENSITIVE.search(title):
        return ("notizia_sicurezza_da_verificare",
                "Verificare aggiornamenti, vendor e advisory ufficiale.")
    return ("approfondimento_con_fonti",
            "Valutare se aggiungere solo contesto utile documentato e fonti affidabili.")


def links_for_short(target: dict, inventory: list[dict]) -> list[dict]:
    """Solo suggerimenti: mai inserimento automatico di link in vecchi post."""
    head = str(target.get("title") or "")
    tokens = topic_tokens(head)
    if len(tokens) < 2:
        return []
    similar = []
    for other in inventory:
        if other["id"] == target["id"] or not site_url(str(other.get("url") or "")):
            continue
        overlap = topic_tokens(str(other.get("title") or "")) & tokens
        # I nomi di prodotti contano; due parole generiche non bastano.
        if len(overlap) >= 3 or (len(overlap) >= 2 and any(
                re.search(r"\d", part) for part in overlap)):
            similar.append({
                "title": other["title"], "url": other["url"], "overlap": len(overlap)
            })
    similar.sort(key=lambda item: item["overlap"], reverse=True)
    return similar[:3]


def description_from_existing(post: dict) -> tuple[str, str]:
    """Ritaglia esclusivamente testo già pubblicato; niente generazione AI."""
    full_title = plain((post.get("title") or {}).get("rendered") or "")
    content_html = (post.get("content") or {}).get("rendered") or ""
    excerpt_html = (post.get("excerpt") or {}).get("rendered") or ""
    paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", content_html, flags=re.I | re.S)
    sources = [plain(excerpt_html)] + [plain(p) for p in paragraphs[:4]]
    if not paragraphs:
        sources.append(plain(content_html)[:1000])
    for source in sources:
        source = re.sub(r"\s+", " ", source).strip()
        if (len(source) < 85 or INSTANT_PROMO.search(source[:170])
                or INTERNAL_NOTES.search(source[:170])):
            continue
        # Non alterare i fatti: usa il prefisso già scritto dall'autore.
        if len(source) > 155:
            shortened = source[:156].rsplit(" ", 1)[0].rstrip(" ,.;:–-")
        else:
            shortened = source.rstrip(" ,.;:–-")
        if not (85 <= len(shortened) <= 155 and len(shortened.split()) >= 12):
            continue
        if len(topic_tokens(full_title) & topic_tokens(shortened)) < 2:
            continue
        if re.search(r"(?:https?://|www\.|<[^>]*>)", shortened, re.I):
            continue
        return shortened, "copia_sintetica_da_excerpt_o_corpo"
    return "", "serve_redazione"


def fetch_html_meta(session: requests.Session, article: dict) -> tuple[dict, str | None]:
    link = str(article.get("url") or "")
    try:
        response = get(session, link)
        if response.status_code != 200:
            return {}, f"Articolo HTTP {response.status_code}"
        parser = PageMeta()
        parser.feed(response.text[:2_000_000])
        return {
            "description": parser.meta.get("description", "").strip(),
            "robots": parser.meta.get("robots", "").strip(),
            "canonical": parser.canonical,
        }, None
    except (requests.RequestException, ValueError, UnicodeError) as exc:
        return {}, str(exc)[:160]


def proposal(post: dict, all_posts: list[dict]) -> dict:
    original = analyze_post(post)
    kind, recommendation = reason_for_article(original["title"])
    suggestion, source = description_from_existing(post)
    return {
        "id": post["id"], "url": original["url"], "title": original["title"],
        "slug": post.get("slug"), "modified": post.get("modified"),
        "words": original["words"], "category_of_review": kind,
        "editorial_recommendation": recommendation,
        "internal_link_suggestions": links_for_short(original, all_posts),
        "meta_description_proposal": suggestion,
        "meta_description_basis": source,
        "current_meta_description": "non_verificata",
        "metadata_status": "not_checked",
    }


def _save_backup(backups: list[dict]) -> None:
    """Salva snapshot sul disco PRIMA di ogni possibile modifica WP."""
    BACKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = BACKUP_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps({
        "site": BASE_URL,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "type": "pre_edit_seo_fields_only",
        "posts": backups,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(BACKUP_FILE)


def apply_meta(session: requests.Session, row: dict, backups: list[dict]) -> str:
    """Scrive SOLTANTO la meta description assente, mai altri campi.

    Una lettura REST autenticata previene modifiche su post cambiati o su
    post senza SEO Bridge. Lo snapshot è persistito prima del POST.
    """
    post_id = int(row["id"])
    if not row.get("meta_description_proposal"):
        return "skipped_no_safe_proposal"
    if row.get("category_of_review") in {
        "offerta_da_ricontrollare", "esperienza_o_recensione_da_attribuire",
    }:
        return "skipped_editorial_review"
    target = urljoin(BASE_URL + "/", f"wp-json/wp/v2/posts/{post_id}")
    response = get(session, target, params={"context": "edit"})
    response.raise_for_status()
    current = response.json()
    if (
        current.get("status") != "publish"
        or current.get("link") != row["url"]
        or current.get("slug") != row["slug"]
        or current.get("modified") != row["modified"]
        or plain((current.get("title") or {}).get("rendered") or "") != row["title"]
    ):
        return "skipped_post_changed"
    seo = current.get("aivision_seo")
    if not isinstance(seo, dict):
        return "skipped_seo_bridge_unavailable"
    if str(seo.get("seo_description") or "").strip():
        return "skipped_description_already_present"
    backups.append({
        "post_id": post_id, "url": row["url"], "slug": row["slug"],
        "previous_aivision_seo": dict(seo),
        "previous_modified": current.get("modified"),
    })
    _save_backup(backups)
    description = row["meta_description_proposal"]
    result = session.post(
        target, params={"context": "edit"},
        # Sending the entire SEO object can erase other fields on the bridge:
        # post only the missing description.
        json={"aivision_seo": {"seo_description": description}},
        timeout=TIMEOUT, allow_redirects=False,
    )
    result.raise_for_status()
    saved = result.json().get("aivision_seo")
    if not isinstance(saved, dict) or saved.get("seo_description") != description:
        return "write_unconfirmed_check_wordpress"
    for key in ("seo_title", "focus_keyphrase"):
        if str(saved.get(key) or "") != str(seo.get(key) or ""):
            return "write_unconfirmed_existing_seo_changed"
    return "updated"


def _live_meta_for_row(row: dict) -> tuple[int, dict, str | None]:
    """Una sessione distinta per ogni thread evita condivisione di stato HTTP."""
    with requests.Session() as session:
        session.headers["User-Agent"] = UA
        meta, error = fetch_html_meta(session, row)
        return int(row["id"]), meta, error


def inspect_all_metadata(rows: list[dict]) -> dict[int, tuple[dict, str | None]]:
    """Verifica tutte le descrizioni, non solo gli articoli cortissimi."""
    found: dict[int, tuple[dict, str | None]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_META_SCAN_WORKERS) as pool:
        for post_id, meta, error in pool.map(_live_meta_for_row, rows):
            found[post_id] = (meta, error)
    return found


def main(argv: list[str] | None = None) -> int:
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("--apply-meta", action="store_true",
                           help="Aggiorna soltanto metadescrizioni mancanti già documentate")
    arguments.add_argument("--limit", type=int, default=MAX_APPLY)
    arguments.add_argument("--output", type=Path, default=OUTPUT_FILE)
    opts = arguments.parse_args(argv)
    if not 1 <= opts.limit <= MAX_APPLY:
        raise ValueError("Limite di aggiornamenti fuori scala (max 6).")
    if opts.apply_meta and os.environ.get("SEO_ARCHIVE_ALLOW_WRITES") != "YES":
        raise PermissionError("Per modificare metadati serve SEO_ARCHIVE_ALLOW_WRITES=YES.")
    if BACKUP_FILE.is_file():
        BACKUP_FILE.unlink()
    session = requests.Session()
    session.headers["User-Agent"] = UA
    if opts.apply_meta:
        username = os.environ.get("WP_USERNAME", "").strip()
        password = os.environ.get("WP_APP_PASSWORD", "").strip()
        configured_base = os.environ.get("WP_BASE_URL", "").strip().rstrip("/")
        if configured_base.endswith("/wp-json"):
            configured_base = configured_base[:-len("/wp-json")]
        if configured_base != BASE_URL or not username or not password:
            raise ValueError("Credenziali WordPress o dominio non configurati in modo sicuro.")
        session.auth = HTTPBasicAuth(username, password)

    posts, diagnostic = archive(session)
    if not diagnostic["complete"]:
        raise RuntimeError("Inventario WordPress incompleto: nessun intervento consentito.")
    all_records = [analyze_post(post) for post in posts]
    short_posts = [post for post, record in zip(posts, all_records)
                   if record["words"] < MAX_SHORT]
    short_posts.sort(key=lambda post: analyze_post(post)["words"])
    short_records = [proposal(post, all_records) for post in short_posts]

    # Tutte le pagine devono essere controllate: anche i post lunghi possono
    # mancare di metadescrizione. Si usa una lettura parallela LIMITATA.
    scan_rows = [{
        "id": post["id"], "url": post.get("link"), "title": plain(
            (post.get("title") or {}).get("rendered") or ""
        )
    } for post in posts]
    checked = inspect_all_metadata(scan_rows)
    missing: list[dict] = []
    http_errors = []
    short_ids = {x["id"] for x in short_records}
    records_by_id = {x["id"]: x for x in short_records}
    for post in posts:
        post_id = int(post["id"])
        meta, error = checked.get(post_id, ({}, "Pagina non verificata"))
        if error:
            http_errors.append({"post_id": post_id, "error": error})
            if post_id in short_ids:
                records_by_id[post_id]["metadata_status"] = "html_unavailable"
            continue
        if meta.get("robots", "").lower().find("noindex") >= 0:
            # Non tentare di cambiare plugin SEO, robots o visibilità in automatico.
            continue
        if not meta.get("description"):
            item = records_by_id.get(post_id) or proposal(post, all_records)
            item["current_meta_description"] = ""
            item["metadata_status"] = ("proposal_only" if item["meta_description_proposal"]
                                       else "requires_editorial_review")
            missing.append(item)
        elif post_id in short_ids:
            records_by_id[post_id]["current_meta_description"] = meta["description"]
            records_by_id[post_id]["metadata_status"] = "already_present"

    # I post con meno parole hanno precedenza: massimo sei metadati per run,
    # ma le OFFERTE obsolete e le recensioni non verificate restano da valutare.
    missing.sort(key=lambda row: (row["words"], row["id"]))
    backups: list[dict] = []
    applied = 0
    errors: list[dict] = []
    for row in missing:
        if not row["meta_description_proposal"]:
            continue
        if row["category_of_review"] in {
            "offerta_da_ricontrollare", "esperienza_o_recensione_da_attribuire",
        }:
            row["metadata_status"] = "requires_editorial_review"
            continue
        if not opts.apply_meta or applied >= opts.limit:
            continue
        try:
            status = apply_meta(session, row, backups)
            row["metadata_status"] = status
            if status == "updated":
                applied += 1
            if status.startswith("write_unconfirmed"):
                errors.append({"id": row["id"], "error": status})
                break
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            row["metadata_status"] = "update_error"
            row["metadata_error"] = f"{type(exc).__name__}: {str(exc)[:150]}"
            errors.append({"id": row["id"], "error": row["metadata_error"]})
            # Stop on uncertainty; never continue a potentially corrupt batch.
            break

    counts = collections.Counter(row["category_of_review"] for row in short_records)
    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "site": BASE_URL, "mode": "meta_updates" if opts.apply_meta else "dry_run",
        "complete_inventory": True, "total_public_posts": len(posts),
        "pages_html_checked": len(checked), "pages_html_errors": http_errors[:100],
        "short_posts": len(short_records), "short_threshold_words": MAX_SHORT,
        "review_categories": dict(counts), "meta_updates_confirmed": applied,
        "meta_missing_count": len(missing),
        "meta_missing_outside_short_posts": sum(x["id"] not in short_ids for x in missing),
        "missing_meta_proposals": sum(x["metadata_status"] == "proposal_only" for x in missing),
        "meta_editorial_review_needed": sum(
            x["metadata_status"] == "requires_editorial_review" for x in missing),
        "backups": backups, "errors": errors,
        "missing_meta_posts": missing,
        "posts": short_records,
        "not_done": [
            "Non si allungano automaticamente articoli né si cambiano titoli/URL.",
            "Le offerte scadute e le recensioni richiedono fonti prima di modificare i fatti.",
            "Google non stabilisce un minimo di parole SEO: nessun testo riempitivo.",
            "Search Console è necessaria per verificare l'indicizzazione reale.",
        ],
    }
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    opts.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SEO ARCHIVIO: {len(posts)} articoli; {len(short_records)} sotto {MAX_SHORT} parole.")
    print("Raggruppamento:", dict(counts))
    print(f"Pagine HTML: {len(checked)}, errori: {len(http_errors)}")
    print(f"Metadescrizioni mancanti: {len(missing)}; aggiornate: {applied}")
    for row in missing:
        print(f"  [{row['id']}] {row['words']} parole | {row['metadata_status']} | "
              f"{row['category_of_review']} | {row['title'][:85]}")
    print("Report:", opts.output)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
