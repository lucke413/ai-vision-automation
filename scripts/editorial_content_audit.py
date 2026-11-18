#!/usr/bin/env python3
"""Audit editoriale completo e in sola lettura degli articoli pubblicati AI Vision.

Non modifica WordPress e non formula giudizi automatici di conformità AdSense.
Produce segnali verificabili per dare priorità alla revisione umana.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import hashlib
import html
import itertools
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

if __package__:
    from .amazon_affiliate import DISCLOSURE, tracking_tag
else:
    from amazon_affiliate import DISCLOSURE, tracking_tag

BASE_URL = "https://aivision.altervista.org"
OUTPUT_JSON = Path("data/editorial_content_audit.json")
OUTPUT_CSV = Path("data/editorial_content_audit.csv")
USER_AGENT = "AIVision-Editorial-Content-Audit/1.0 (read-only)"
TIMEOUT = (6, 20)
MAX_POSTS = 1000
MIN_DUPLICATE_WORDS = 250
MIN_DUPLICATE_JACCARD = 0.36
SECURITY_UPDATE_MARKER = "<!-- ai-vision-security-update:v1 -->"

WORD_RE = re.compile(r"[a-z0-9à-öø-ÿ]+", re.I)
OFFER_RE = re.compile(
    r"\b(?:in offerta|offerta\s+(?:su|amazon|prime)|"
    r"offerta\s+(?:al\s+(?:minimo storico|prezzo)|a\s+\d{1,3})|"
    r"scont[oi]\s+(?:del|di|fino|a)\s+\d{1,3}(?:[.,]\d+)?|"
    r"coupon|codice promozionale|prezzo minimo|prezzo speciale|al minimo storico|"
    r"black friday|prime day|offerte prime|ribasso del \d{1,3}|"
    r"promozione amazon|promozione prime)\b", re.I
)
INSTANT_PROMO_RE = re.compile(
    r"\b(?:solo oggi|scade oggi|ultime ore (?:di|per|dell')|acquista subito|"
    r"fino a mezzanotte|offerta lampo|scade il \d{1,2})\b", re.I
)
HISTORICAL_CONTEXT_RE = re.compile(
    r"\b(?:era disponibile|era in offerta|era stata proposta|era stato proposto|"
    r"si è conclus[ao]|si è chius[ao]|offerta scaduta|promozione terminata|"
    r"non è più attiva|non è una quotazione attuale|prezzo storico|"
    r"all'epoca|in quella data|in quell'occasione|prezzo segnalato il|"
    r"si riferiscono a quanto segnalato il|promozioni e disponibilità possono essere cambiate|"
    r"vecchia versione (?:di questa pagina|della pagina)|non va presentato come un'offerta ancora attiva|"
    r"l'offerta risale|ultimo giorno utile|ultima giornata|evento volge al termine|"
    r"fino alle 23:59|fino al \d{1,2}\b)\b", re.I
)
FIRST_HAND_RE = re.compile(
    r"\b(?:abbiamo (?:provato|testato|misurato|verificato|utilizzato|apprezzato|"
    r"notato|osservato|riscontrato|rilevato|constatato|valutato|trovato)|"
    r"nel nostro test|nel nostro utilizzo|durante la nostra prova|nelle nostre prove|"
    r"la nostra prova|ci è sembrat[oa]|ci ha convinto|ci ha colpito)\b", re.I
)
INTERNAL_NOTE_RE = re.compile(
    r"\b(?:prima della pubblicazione|bozza interna|istruzioni redazionali|"
    r"fonte fornita|dati della fonte|fact[ -]?check interno)\b", re.I
)
AFFILIATE_RE = re.compile(
    r"\b(?:link|collegament[oi])\s+(?:di\s+)?affiliat[oi]\b|"
    r"\b(?:potremmo|possiamo) ricevere (?:una )?commissione\b", re.I
)
REVIEW_TITLE_RE = re.compile(r"\b(?:recensione|in prova|test completo|prova su strada)\b", re.I)
# Segnala eventi o avvisi di sicurezza realmente datati, non articoli prodotto
# che menzionano genericamente patch, sicurezza o phishing come tema evergreen.
SECURITY_RE = re.compile(
    r"\b(?:CVE-\d{4}-\d{4,7}|zero[- ]day|ransomware|data breach|"
    r"violazione dei dati|fuga di dati|ShinyHunters|fine del supporto|"
    r"fine degli aggiornamenti|end of support)\b", re.I
)
MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5,
    "giugno": 6, "luglio": 7, "agosto": 8, "settembre": 9,
    "ottobre": 10, "novembre": 11, "dicembre": 12,
}

VERIFIED_DATE_RE = re.compile(
    r"\b(?:al momento del controllo|prezzo verificato|prezzo controllato|ricontrollato)"
    r"\s+(?:(?:il|del)\s+)?(\d{1,2})\s+"
    r"(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
    r"\s+(\d{4})\b",
    re.I,
)


def has_recent_price_check(text: str, today: dt.date, max_age_days: int = 7) -> bool:
    for match in VERIFIED_DATE_RE.finditer(text or ""):
        try:
            checked = dt.date(
                int(match.group(3)),
                MONTHS[match.group(2).casefold()],
                int(match.group(1)),
            )
        except (KeyError, ValueError):
            continue
        age = (today - checked).days
        if 0 <= age <= max_age_days:
            return True
    return False



def plain(value: str) -> str:
    raw = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", value or "", flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return " ".join(html.unescape(raw).split())


def tokens(value: str) -> list[str]:
    return WORD_RE.findall(plain(value).casefold())


def shingles(value: str, size: int = 5) -> set[tuple[str, ...]]:
    words = tokens(value)
    return {tuple(words[i:i + size]) for i in range(max(0, len(words) - size + 1))}


class BodyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.images = 0
        self.images_missing_alt = 0
        self.h2 = 0
        self.h3 = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(str(attrs["href"]))
        elif tag == "img":
            self.images += 1
            if not str(attrs.get("alt") or "").strip():
                self.images_missing_alt += 1
        elif tag == "h2":
            self.h2 += 1
        elif tag == "h3":
            self.h3 += 1


def evidence_for(pattern: re.Pattern, text: str, radius: int = 100) -> str:
    match = pattern.search(text or "")
    if not match:
        return (text or "")[:240]
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end]


def add_flag(flags: list[dict], code: str, severity: str, message: str, evidence: str = ""):
    flags.append({
        "code": code,
        "severity": severity,
        "message": message,
        "evidence": evidence[:240],
    })


def analyze_post(post: dict, today: dt.date | None = None) -> dict:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    title = plain((post.get("title") or {}).get("rendered") or "")
    body_html = (post.get("content") or {}).get("rendered") or ""
    body_text = plain(body_html)
    body_without_links = plain(re.sub(r"<a\b[^>]*>.*?</a>", " ", body_html, flags=re.I | re.S))
    excerpt = plain((post.get("excerpt") or {}).get("rendered") or "")
    parser = BodyParser()
    parser.feed(body_html)

    host = urlsplit(BASE_URL).hostname
    internal_links, external_links = set(), set()
    for href in parser.links:
        full = urljoin(str(post.get("link") or BASE_URL), href)
        parsed = urlsplit(full)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        if parsed.hostname.casefold() == (host or "").casefold():
            internal_links.add(parsed.path.rstrip("/") or "/")
        else:
            external_links.add(full)

    words = len(tokens(body_html))
    published = str(post.get("date") or "")
    try:
        published_date = dt.datetime.fromisoformat(published.replace("Z", "+00:00")).date()
        age_days = max(0, (today - published_date).days)
    except ValueError:
        published_date, age_days = None, None

    flags: list[dict] = []
    if words < 300:
        add_flag(flags, "very_short_content", "medium", "Corpo sotto 300 parole: verificare se risponde davvero alla domanda.")
    elif words < 400:
        add_flag(flags, "short_content_review", "low", "Corpo sotto 400 parole: verificare completezza e utilità, senza allungare artificialmente.")

    if words >= 500 and parser.h2 == 0:
        add_flag(flags, "missing_h2", "low", "Articolo lungo senza sottotitoli H2 nel corpo.")
    if not internal_links:
        add_flag(flags, "no_internal_links", "low", "Nessun collegamento interno nel corpo.")
    if not external_links:
        add_flag(flags, "no_external_references", "medium", "Nessun collegamento esterno: controllare attribuzione e fonti.")
    if parser.images_missing_alt:
        add_flag(flags, "images_missing_alt", "low", f"{parser.images_missing_alt} immagini senza testo alternativo.")
    if not post.get("featured_media"):
        add_flag(flags, "missing_featured_image", "low", "Immagine in evidenza assente.")

    title_and_body = title + " " + body_without_links
    has_offer = bool(OFFER_RE.search(title_and_body))
    has_historical_context = (
        bool(HISTORICAL_CONTEXT_RE.search(body_without_links))
        or has_recent_price_check(body_without_links, today)
    )
    if has_offer and age_days is not None and age_days > 21 and not has_historical_context:
        add_flag(flags, "stale_offer_review", "high",
                 "Contenuto commerciale pubblicato da oltre 21 giorni senza chiara indicazione storica.",
                 evidence_for(OFFER_RE, title_and_body))
    if has_offer and INSTANT_PROMO_RE.search(title_and_body) and age_days is not None and age_days > 2 and not has_historical_context:
        add_flag(flags, "likely_expired_promo", "high",
                 "Formula promozionale immediata in un articolo non recente: verificare o aggiornare.",
                 evidence_for(INSTANT_PROMO_RE, title_and_body))
    if FIRST_HAND_RE.search(body_without_links):
        add_flag(flags, "first_hand_claim_attribution", "high",
                 "Il corpo contiene una dichiarazione di prova diretta: verificare che sia documentata e attribuita.",
                 evidence_for(FIRST_HAND_RE, body_without_links))
    elif REVIEW_TITLE_RE.search(title):
        add_flag(flags, "review_title_attribution_review", "medium",
                 "Il titolo presenta il contenuto come recensione/prova: verificare che non suggerisca test diretti non documentati.",
                 title)
    if INTERNAL_NOTE_RE.search(body_without_links):
        add_flag(flags, "editorial_note_in_public_text", "high",
                 "Possibile nota redazionale o istruzione interna nel testo pubblico.",
                 evidence_for(INTERNAL_NOTE_RE, body_without_links))
    verified_affiliate = DISCLOSURE in body_text and any(
        link.startswith("https://") and tracking_tag(link) for link in parser.links
    )
    if AFFILIATE_RE.search(body_text) and not verified_affiliate:
        add_flag(flags, "affiliate_disclosure_check", "high",
                 "Il testo parla di link affiliati o commissioni: verificare che i link e la disclosure esistano davvero.",
                 evidence_for(AFFILIATE_RE, body_text))
    if (SECURITY_RE.search(title_and_body) and age_days is not None and age_days > 30
            and SECURITY_UPDATE_MARKER not in body_html):
        add_flag(flags, "security_update_review", "medium",
                 "Notizia di sicurezza oltre 30 giorni: controllare advisory, patch e stato attuale.",
                 evidence_for(SECURITY_RE, title_and_body))

    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    priority = max((severity_rank.get(x["severity"], 0) for x in flags), default=0)
    return {
        "id": post.get("id"),
        "title": title,
        "slug": post.get("slug"),
        "url": post.get("link"),
        "date": published,
        "modified": post.get("modified"),
        "age_days": age_days,
        "words": words,
        "excerpt_length": len(excerpt),
        "h2": parser.h2,
        "h3": parser.h3,
        "internal_links": len(internal_links),
        "external_links": len(external_links),
        "images": parser.images,
        "images_missing_alt": parser.images_missing_alt,
        "featured_media": post.get("featured_media"),
        "priority": priority,
        "flags": flags,
        "body_text": body_text,
    }


def fetch_posts() -> tuple[list[dict], dict]:
    endpoint = BASE_URL + "/wp-json/wp/v2/posts"
    session = requests.Session()
    # Bypass AlterVista/CDN cached REST responses after authenticated WordPress writes.
    cache_bust = str(int(dt.datetime.now(dt.timezone.utc).timestamp() * 1_000_000))
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
    })
    posts: list[dict] = []
    seen: set[int] = set()
    info = {"endpoint": endpoint, "pages": 0, "total_header": None, "complete": False, "errors": []}
    for page in range(1, 1 + (MAX_POSTS + 99) // 100):
        response = session.get(endpoint, params={
            "status": "publish", "per_page": 100, "page": page,
            "orderby": "id", "order": "asc",
            "_fields": "id,title,content,excerpt,link,slug,date,modified,featured_media",
            "_av_audit_bust": cache_bust,
        }, timeout=TIMEOUT)
        if response.status_code == 400 and posts:
            try:
                code = response.json().get("code")
            except (ValueError, AttributeError):
                code = ""
            if code == "rest_post_invalid_page_number":
                break
        response.raise_for_status()
        values = response.json()
        if not isinstance(values, list):
            raise RuntimeError(f"Pagina {page}: risposta REST non valida.")
        total = response.headers.get("X-WP-Total")
        if total and total.isdigit():
            info["total_header"] = int(total)
        info["pages"] += 1
        if not values:
            break
        ids = [x.get("id") for x in values if isinstance(x, dict)]
        if len(ids) != len(values) or any(not isinstance(x, int) for x in ids):
            raise RuntimeError(f"Pagina {page}: record senza ID valido.")
        duplicate_ids = seen.intersection(ids)
        if duplicate_ids:
            raise RuntimeError(f"Paginazione REST ripetuta: ID {sorted(duplicate_ids)[:5]}.")
        seen.update(ids)
        posts.extend(values)
        if info["total_header"] is not None and len(posts) >= info["total_header"]:
            break
        if len(values) < 100:
            break
        if len(posts) >= MAX_POSTS:
            raise RuntimeError(f"Archivio oltre il limite di sicurezza ({MAX_POSTS}).")
    info["retrieved"] = len(posts)
    info["complete"] = (
        not info["errors"]
        and ((info["total_header"] is not None and len(posts) == info["total_header"])
             or (info["total_header"] is None and bool(posts) and len(posts) % 100 != 0))
    )
    if not info["complete"]:
        info["errors"].append("Copertura archivio non dimostrata: report non utilizzabile come inventario completo.")
    return posts, info


def find_similar_bodies(records: list[dict]) -> list[dict]:
    candidates = [x for x in records if x["words"] >= MIN_DUPLICATE_WORDS]
    shingle_sets = {x["id"]: shingles(x["body_text"]) for x in candidates}
    pairs = []
    for first, second in itertools.combinations(candidates, 2):
        a, b = shingle_sets[first["id"]], shingle_sets[second["id"]]
        if not a or not b:
            continue
        common = len(a & b)
        if common < 25:
            continue
        score = common / len(a | b)
        if score >= MIN_DUPLICATE_JACCARD:
            pairs.append({
                "first_id": first["id"], "second_id": second["id"],
                "first_title": first["title"], "second_title": second["title"],
                "first_url": first["url"], "second_url": second["url"],
                "fivegram_jaccard": round(score, 4),
            })
    return sorted(pairs, key=lambda x: x["fivegram_jaccard"], reverse=True)[:100]


def main() -> int:
    posts, api = fetch_posts()
    if not posts or not api["complete"]:
        raise RuntimeError("Audit interrotto: inventario WordPress incompleto.")
    today = dt.datetime.now(dt.timezone.utc).date()
    records = [analyze_post(post, today) for post in posts]
    counts = collections.Counter(flag["code"] for item in records for flag in item["flags"])
    priorities = collections.Counter(str(item["priority"]) for item in records)
    duplicates = find_similar_bodies(records)
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "site": BASE_URL,
        "readonly": True,
        "inventory": api,
        "limitations": [
            "L'audit usa l'API pubblica WordPress e controlli deterministici; non sostituisce la revisione del testo e delle fonti.",
            "L'assenza di un link esterno non dimostra una violazione; segnala un controllo di attribuzione da fare.",
            "L'audit non può verificare licenze delle immagini dai soli post pubblici.",
            "Non misura indicizzazione o approvazione AdSense: per questo serve Google Search Console e la valutazione Google."
        ],
        "summary": {
            "total_posts": len(records),
            "priority_counts": dict(priorities),
            "findings": dict(counts),
            "similar_body_pairs": len(duplicates),
            "high_priority_posts": sum(item["priority"] >= 3 for item in records),
        },
        "similar_body_pairs": duplicates,
        "posts": records,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "id", "title", "url", "date", "modified", "age_days", "words",
            "internal_links", "external_links", "h2", "images", "priority", "flags",
        ])
        writer.writeheader()
        for item in records:
            writer.writerow({
                **{key: item.get(key) for key in writer.fieldnames if key not in {"flags"}},
                "flags": "; ".join(flag["code"] for flag in item["flags"]),
            })
    print("EDITORIAL CONTENT AUDIT - SOLA LETTURA")
    print("Articoli:", len(records), "/", api.get("total_header"), "copertura completa:", api["complete"])
    print("Priorità:", json.dumps(dict(priorities), ensure_ascii=False))
    print("Segnali:", json.dumps(dict(counts), ensure_ascii=False))
    print("Possibili coppie di contenuti simili:", len(duplicates))
    print("Report:", OUTPUT_JSON)
    print("CSV:", OUTPUT_CSV)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
