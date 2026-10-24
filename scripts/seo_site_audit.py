#!/usr/bin/env python3
"""Audit SEO di tutte le pagine articolo WordPress pubbliche, sola lettura.

Nessun token o credenziale WordPress; nessuna modifica o pubblicazione.
Le API pubbliche coprono ogni articolo; l'HTML live verifica meta, canonical
e robots per ogni URL raggiungibile. Un audit NON equivale a Search Console.
"""
from __future__ import annotations

import collections
import concurrent.futures
import datetime
import difflib
import html
import json
import os
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

BASE_URL = "https://aivision.altervista.org"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "seo_full_audit.json"
USER_AGENT = "AIVision-SEO-Auditor/1.0 (read-only)"
TIMEOUT = (5, 14)
MAX_PUBLIC_POSTS = 1000
MAX_HTML_POSTS = 350
MAX_WORKERS = 3


def get(url: str, **kwargs):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != urlsplit(BASE_URL).hostname:
        raise ValueError("URL esterno/non sicuro escluso dall'audit")
    r = requests.get(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html, application/json"},
        timeout=TIMEOUT, **kwargs
    )
    if urlsplit(r.url).hostname != urlsplit(BASE_URL).hostname:
        raise ValueError("Redirect esterno escluso")
    return r


def plain(value: str) -> str:
    raw = re.sub(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", " ", value or "", flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return " ".join(html.unescape(raw).split())


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ]+(?:['’][\wÀ-ÖØ-öø-ÿ]+)*\b", plain(text)))


def text_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", plain(text).lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text)).strip()


class PageMeta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.canonical = ""
        self.page_title = ""
        self.head_title = False
        self.headings = {"h1": 0, "h2": 0}
        self.lang = ""
        self.structured_data = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.lang = str(attrs.get("lang") or "")
        if tag == "meta":
            key = str(attrs.get("name") or attrs.get("property") or "").lower()
            if key and key not in self.meta:
                self.meta[key] = str(attrs.get("content") or "")
        if tag == "link" and "canonical" in str(attrs.get("rel") or "").lower().split():
            self.canonical = str(attrs.get("href") or "")
        if tag == "title":
            self.head_title = True
        if tag in self.headings:
            self.headings[tag] += 1
        if tag == "script" and str(attrs.get("type") or "").lower() == "application/ld+json":
            self.structured_data += 1

    def handle_data(self, data):
        if self.head_title:
            self.page_title += data

    def handle_endtag(self, tag):
        if tag == "title":
            self.head_title = False


class ArticleHtml(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.images = 0
        self.missing_alt = 0
        self.h2 = 0
        self.h3 = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(str(attrs["href"]))
        if tag == "img":
            self.images += 1
            if not str(attrs.get("alt") or "").strip():
                self.missing_alt += 1
        if tag == "h2":
            self.h2 += 1
        if tag == "h3":
            self.h3 += 1


def analyze_post(post: dict) -> dict:
    body = (post.get("content") or {}).get("rendered") or ""
    title = plain((post.get("title") or {}).get("rendered") or "")
    excerpt = plain((post.get("excerpt") or {}).get("rendered") or "")
    detail = ArticleHtml()
    detail.feed(body)
    own_host = urlsplit(BASE_URL).hostname
    own_links = set()
    external = set()
    for href in detail.links:
        full = urljoin(str(post.get("link") or BASE_URL), href)
        parsed = urlsplit(full)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            continue
        if parsed.hostname == own_host:
            own_links.add(parsed.path.rstrip("/") or "/")
        else:
            external.add(parsed.hostname or "")
    warnings = []
    wc = count_words(body)
    if wc < 300:
        warnings.append("very_short_body")
    elif wc < 500:
        warnings.append("body_under_500")
    if len(title) < 20 or len(title) > 100:
        warnings.append("title_length_unusual")
    if detail.h2 == 0 and wc >= 500:
        warnings.append("no_h2_in_body")
    if detail.images and detail.missing_alt:
        warnings.append("images_without_alt")
    if not own_links:
        warnings.append("no_in_content_internal_links")
    if not external:
        warnings.append("no_in_content_external_links")
    if not post.get("featured_media"):
        warnings.append("missing_featured_image")
    return {
        "id": post.get("id"), "title": title, "date": post.get("date"),
        "modified": post.get("modified"), "url": post.get("link"),
        "slug": post.get("slug"), "words": wc, "excerpt_length": len(excerpt),
        "title_key": text_key(title), "body_hash": text_key(body)[:300],
        "in_content_internal_links": len(own_links),
        "in_content_external_domains": sorted(external)[:30],
        "in_content_external_links": len(external),
        "images": detail.images, "images_missing_alt": detail.missing_alt,
        "featured_image_id": post.get("featured_media"),
        "h2": detail.h2, "h3": detail.h3, "warnings": warnings,
    }


def fetch_posts() -> tuple[list[dict], dict]:
    output = []
    diagnostics = {"endpoint": BASE_URL + "/wp-json/wp/v2/posts", "pages_fetched": 0,
                   "header_total": None, "errors": []}
    for page in range(1, 1 + (MAX_PUBLIC_POSTS + 99) // 100):
        url = diagnostics["endpoint"]
        try:
            r = get(url, params={
                "status": "publish", "per_page": 100, "page": page,
                "_fields": "id,title,content,excerpt,link,slug,date,modified,featured_media",
            })
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list):
                raise ValueError("Inventario REST non contiene una lista")
            total = r.headers.get("X-WP-Total")
            if str(total).isdigit():
                diagnostics["header_total"] = int(total)
            output.extend(data)
            diagnostics["pages_fetched"] += 1
            if len(output) >= MAX_PUBLIC_POSTS or len(data) < 100:
                break
        except (ValueError, requests.RequestException) as exc:
            diagnostics["errors"].append(f"pagina {page}: {type(exc).__name__}: {str(exc)[:160]}")
            break
    diagnostics["retrieved"] = len(output)
    diagnostics["complete"] = (
        not diagnostics["errors"]
        and diagnostics["header_total"] is not None
        and diagnostics["header_total"] == len(output)
    )
    return output, diagnostics


def fetch_live_meta(url: str) -> dict:
    time.sleep(0.2)
    try:
        r = get(url)
        if r.status_code != 200:
            return {"status": r.status_code, "error": f"HTTP {r.status_code}"}
        parser = PageMeta()
        parser.feed(r.text[:3_000_000])
        return {
            "status": 200,
            "canonical": parser.canonical, "meta_description": parser.meta.get("description", ""),
            "meta_robots": parser.meta.get("robots", ""),
            "x_robots": r.headers.get("X-Robots-Tag", ""),
            "html_title": plain(parser.page_title),
            "html_h1": parser.headings["h1"],
            "html_h2": parser.headings["h2"],
            "json_ld_blocks": parser.structured_data, "lang": parser.lang,
        }
    except (ValueError, requests.RequestException, UnicodeError) as exc:
        return {"status": None, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def scan_live_posts(records: list[dict]) -> dict:
    selected = records[:MAX_HTML_POSTS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_live_meta, p["url"]): p["id"] for p in selected}
        result = {post_id: fut.result() for fut, post_id in
                  ((f, futures[f]) for f in concurrent.futures.as_completed(futures))}
    return result


def find_similar(records: list[dict]) -> list[dict]:
    stop = {"come", "della", "delle", "questo", "questa", "con", "per",
            "uno", "una", "nel", "nella", "dopo", "ecco", "nuovo",
            "nuova", "prezzo", "offerta", "recensione", "guida"}
    tokens = []
    for r in records:
        tokens.append({t for t in r["title_key"].split() if len(t) > 2 and t not in stop})
    matches = []
    for i, a in enumerate(records):
        for j in range(i + 1, len(records)):
            b = records[j]
            common = tokens[i] & tokens[j]
            if len(common) < 3:
                continue
            overlap = len(common) / max(1, min(len(tokens[i]), len(tokens[j])))
            ratio = difflib.SequenceMatcher(None, a["title_key"], b["title_key"]).ratio()
            if overlap >= .78 and ratio >= .50 or ratio >= .83:
                matches.append({
                    "first_id": a["id"], "second_id": b["id"],
                    "first_title": a["title"], "second_title": b["title"],
                    "first_url": a["url"], "second_url": b["url"],
                    "similarity": round(max(overlap, ratio), 2)
                })
    return sorted(matches, key=lambda x: x["similarity"], reverse=True)[:80]


def site_files() -> dict:
    result = {}
    for path in ("/robots.txt", "/sitemap_index.xml", "/chi-sono/"):
        try:
            r = get(BASE_URL + path)
            info = {"status": r.status_code}
            if path == "/robots.txt":
                info["text"] = r.text[:10000]
            if path.endswith(".xml") and r.status_code == 200:
                try:
                    root = ET.fromstring(r.text)
                    info["sitemap_urls"] = [n.text for n in root.iter()
                                            if n.tag.endswith("loc") and n.text][:50]
                except ET.ParseError:
                    info["xml_parse_error"] = True
            result[path] = info
        except (requests.RequestException, ValueError) as exc:
            result[path] = {"error": str(exc)[:150]}
    return result


def build_report(posts: list[dict], diagnostic: dict, live: dict, static: dict) -> dict:
    items = [analyze_post(p) for p in posts]
    counter = collections.Counter(w for p in items for w in p["warnings"])
    keys = collections.defaultdict(list)
    for item in items:
        keys[item["title_key"]].append(item["url"])
    duplicates = [urls for urls in keys.values() if len(urls) >= 2]
    live_counter = collections.Counter()
    live_issues = []
    for item in items:
        status = live.get(item["id"])
        if status is None:
            continue
        if status.get("status") != 200:
            live_counter["non_200"] += 1
            live_issues.append({"url": item["url"], "issue": status.get("error", "not 200")})
            continue
        if not status.get("meta_description"):
            live_counter["missing_description"] += 1
        elif len(status["meta_description"]) > 175:
            live_counter["long_description"] += 1
        if not status.get("canonical"):
            live_counter["missing_canonical"] += 1
        elif status["canonical"].rstrip("/") != item["url"].rstrip("/"):
            live_counter["non_self_canonical"] += 1
            live_issues.append({
                "url": item["url"], "issue": "canonical_different",
                "canonical": status["canonical"],
            })
        if "noindex" in (status.get("meta_robots", "") + " " + status.get("x_robots", "")).lower():
            live_counter["noindex"] += 1
            live_issues.append({"url": item["url"], "issue": "noindex"})
        if not status.get("html_title"):
            live_counter["missing_html_title"] += 1
        if status.get("html_h1", 0) != 1:
            live_counter["non_single_h1"] += 1
        if not status.get("json_ld_blocks"):
            live_counter["no_json_ld"] += 1
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "site": BASE_URL,
        "readonly": True,
        "limitations": [
            "Non misura le URL indicizzate: verificare Google Search Console.",
            "Non verifica l'attendibilita fattuale degli articoli o le prestazioni Lighthouse.",
            "Similarita titoli = segnale editoriale, non penalizzazione Google automatica."
        ],
        "api": diagnostic, "files": static,
        "summary": {
            "total_posts": len(items), "total_api_reported": diagnostic["header_total"],
            "content_words_under_300": sum(x["words"] < 300 for x in items),
            "content_words_300_499": sum(300 <= x["words"] < 500 for x in items),
            "content_words_500_649": sum(500 <= x["words"] < 650 for x in items),
            "content_words_650_plus": sum(x["words"] >= 650 for x in items),
            "same_titles": len(duplicates), "similar_titles": len(find_similar(items)),
            "html_checked": len(live), "html_ok": sum(v.get("status") == 200 for v in live.values()),
            "html_findings": dict(live_counter), "content_findings": dict(counter),
        },
        "exact_duplicate_titles": duplicates,
        "similar_titles": find_similar(items),
        "page_issues": live_issues[:200],
        "posts": [{
            **{k: v for k, v in x.items() if k not in {"title_key", "body_hash"}},
            "seo": live.get(x["id"]),
        } for x in items],
    }


def main() -> int:
    posts, diagnosis = fetch_posts()
    if not posts:
        raise RuntimeError("Nessun articolo recuperato: audit incompleto.")
    analyzed = [analyze_post(p) for p in posts]
    live = scan_live_posts(analyzed)
    static = site_files()
    report = build_report(posts, diagnosis, live, static)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SEO AUDIT - SOLA LETTURA")
    print("Articoli:", report["summary"]["total_posts"],
          "dei", report["summary"]["total_api_reported"], "attesi; copertura:",
          "completa" if report["api"]["complete"] else "PARZIALE")
    print("HTML verificato:", report["summary"]["html_checked"],
          "con HTTP 200:", report["summary"]["html_ok"])
    print("Parole <300 / 300-499 / 500-649 / >=650:",
          report["summary"]["content_words_under_300"],
          report["summary"]["content_words_300_499"],
          report["summary"]["content_words_500_649"],
          report["summary"]["content_words_650_plus"])
    print("Titoli simili:", report["summary"]["similar_titles"],
          "identici:", report["summary"]["same_titles"])
    print("Segnali contenuto:", json.dumps(report["summary"]["content_findings"]))
    print("Segnali meta:", json.dumps(report["summary"]["html_findings"]))
    for x in report["similar_titles"][:12]:
        print("POSSIBILE SOVRAPPOSIZIONE:", x["first_title"], "|", x["second_title"])
    for x in report["page_issues"][:12]:
        print("ATTENZIONE:", x)
    print("Report:", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
