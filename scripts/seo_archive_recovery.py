#!/usr/bin/env python3
"""Recupero SEO archivio AIVision: analisi completa e metadati opt-in.

Default: SOLA LETTURA, nessuna variazione agli articoli.
La modalità --apply-meta può compilare SOLO meta description già assenti,
sfruttando testo presente nell'articolo, senza inventare informazioni.
Niente allungamenti a un conteggio artificiale, link affiliati, redirect,
cambi di slug/status/data/titolo, modifiche al corpo o rimozioni.
"""
from __future__ import annotations

import argparse
import collections
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


def apply_meta(session: requests.Session, row: dict, backups: list[dict]) -> str:
    """Aggiorna SOLO aivision_seo preservando titoli, contenuto e altre proprietà."""
    post_id = int(row["id"])
    target = urljoin(BASE_URL + "/", f"wp-json/wp/v2/posts/{post_id}")
    response = get(session, target, params={"context": "edit"})
    response.raise_for_status()
    current = response.json()
    if (current.get("status") != "publish"
            or current.get("link") != row["url"]
            or current.get("modified") != row["modified"]):
        return "skipped_post_changed"
    seo = current.get("aivision_seo")
    if not isinstance(seo, dict):
        return "skipped_seo_bridge_unavailable"
    if str(seo.get("seo_description") or "").strip():
        return "skipped_description_already_present"
    # Snapshot del solo payload SEO preesistente prima di qualsiasi POST.
    backups.append({
        "post_id": post_id, "url": row["url"], "previous_aivision_seo": seo,
        "previous_modified": current.get("modified"),
    })
    new_fields = dict(seo)
    new_fields["seo_description"] = row["meta_description_proposal"]
    result = session.post(
        target, params={"context": "edit"},
        json={"aivision_seo": new_fields}, timeout=TIMEOUT, allow_redirects=False,
    )
    result.raise_for_status()
    saved = result.json().get("aivision_seo")
    if not isinstance(saved, dict) or saved.get("seo_description") != new_fields["seo_description"]:
        return "write_unconfirmed_check_wordpress"
    for key in ("seo_title", "focus_keyphrase"):
        if str(saved.get(key) or "") != str(seo.get(key) or ""):
            return "write_unconfirmed_existing_seo_changed"
    return "updated"


def main(argv: list[str] | None = None) -> int:
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("--apply-meta", action="store_true",
                           help="Salva metadescrizioni già assenti, solo su esplicita richiesta")
    arguments.add_argument("--limit", type=int, default=MAX_APPLY)
    arguments.add_argument("--output", type=Path, default=OUTPUT_FILE)
    opts = arguments.parse_args(argv)
    if not 1 <= opts.limit <= MAX_APPLY:
        raise ValueError("Limite di aggiornamenti fuori scala (max 6).")
    if opts.apply_meta and os.environ.get("SEO_ARCHIVE_ALLOW_WRITES") != "YES":
        raise PermissionError("Per modificare metadati serve SEO_ARCHIVE_ALLOW_WRITES=YES.")
    session = requests.Session()
    session.headers["User-Agent"] = UA
    if opts.apply_meta:
        username = os.environ.get("WP_USERNAME", "").strip()
        password = os.environ.get("WP_APP_PASSWORD", "").strip()
        configured_base = os.environ.get("WP_BASE_URL", "").strip().rstrip("/")
        if configured_base != BASE_URL or not username or not password:
            raise ValueError("Credenziali WordPress o dominio non configurati in modo sicuro.")
        session.auth = HTTPBasicAuth(username, password)

    posts, diagnostic = archive(session)
    if not diagnostic["complete"]:
        raise RuntimeError("Inventario WordPress incompleto: nessun intervento consentito.")
    all_records = [analyze_post(post) for post in posts]
    originals = [post for post, record in zip(posts, all_records)
                 if record["words"] < MAX_SHORT]
    # Prima i contenuti più brevi, non per forza quelli più recenti.
    originals.sort(key=lambda post: analyze_post(post)["words"])
    records = [proposal(post, all_records) for post in originals]
    backups: list[dict] = []
    applied = 0
    for row in records:
        meta, error = fetch_html_meta(session, row)
        if error:
            row["metadata_status"] = "html_unavailable"
            row["metadata_error"] = error
            continue
        row["current_meta_description"] = meta["description"]
        if meta["description"]:
            row["metadata_status"] = "already_present"
            continue
        if not row["meta_description_proposal"]:
            row["metadata_status"] = "requires_editorial_review"
            continue
        row["metadata_status"] = "proposal_only"
        if opts.apply_meta and applied < opts.limit:
            try:
                status = apply_meta(session, row, backups)
                row["metadata_status"] = status
                if status == "updated":
                    applied += 1
            except (requests.RequestException, ValueError, KeyError) as exc:
                row["metadata_status"] = "update_error"
                row["metadata_error"] = f"{type(exc).__name__}: {str(exc)[:150]}"
                # Stop on first failure: prevent a batch of uncertain writes.
                break

    counts = collections.Counter(row["category_of_review"] for row in records)
    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "site": BASE_URL, "mode": "meta_updates" if opts.apply_meta else "dry_run",
        "complete_inventory": True, "total_public_posts": len(posts),
        "short_posts": len(records), "short_threshold_words": MAX_SHORT,
        "review_categories": dict(counts), "meta_updates_confirmed": applied,
        "missing_meta_proposals": sum(x["metadata_status"] == "proposal_only" for x in records),
        "meta_editorial_review_needed": sum(
            x["metadata_status"] == "requires_editorial_review" for x in records),
        "backups": backups, "posts": records,
        "not_done": [
            "Non si espandono testi, non si fanno redirect e non si rimuovono post.",
            "Le offerte datate richiedono verifica prezzi e condizioni prima di ogni ampliamento.",
            "Il numero di parole non rappresenta un requisito SEO Google.",
            "Controllare il sito live e Search Console dopo qualunque aggiornamento.",
        ],
    }
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    opts.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SEO ARCHIVIO: {len(posts)} articoli, {len(records)} sotto {MAX_SHORT} parole.")
    print("Raggruppamento:", dict(counts))
    print("Metadati aggiornati:", applied)
    for row in records:
        print(f"  [{row['id']}] {row['words']} parole | {row['metadata_status']} | "
              f"{row['category_of_review']} | {row['title'][:85]}")
    print("Report:", opts.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
