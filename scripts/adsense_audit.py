#!/usr/bin/env python3
"""Audit tecnico pubblico del sito per la revisione AdSense.

Non modifica WordPress e non usa credenziali. Controlla raggiungibilita',
crawler, segnali noindex, collegamento AdSense, ads.txt, sitemap, privacy
e una fotografia quantitativa dei contenuti WordPress.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

BASE_URL = os.environ.get("ADSENSE_SITE_URL", "https://aivision.altervista.org").rstrip("/")
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "adsense_audit.json"
TIMEOUT = (8, 20)
UA_BROWSER = "Mozilla/5.0 (compatible; AI-Vision-AdSense-Audit/1.0)"
UA_MEDIA = "Mediapartners-Google"
UA_DISPLAY = "Google-Display-Ads-Bot"

WORD_RE = re.compile(r"\b[\wÀ-ÖØ-öø-ÿ]+(?:['’\-][\wÀ-ÖØ-öø-ÿ]+)*\b", re.UNICODE)
TAG_RE = re.compile(r"<[^>]+>")
PUB_RE = re.compile(r"(?:ca-)?pub-\d{10,}", re.I)


def get(path: str, user_agent: str = UA_BROWSER) -> dict:
    url = path if path.startswith("http") else urljoin(BASE_URL + "/", path.lstrip("/"))
    try:
        r = requests.get(
            url,
            headers={"User-Agent": user_agent, "Accept": "*/*"},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        return {
            "ok": True,
            "status": r.status_code,
            "url": url,
            "final_url": r.url,
            "content_type": r.headers.get("Content-Type", ""),
            "x_robots_tag": r.headers.get("X-Robots-Tag", ""),
            "text": r.text[:2_500_000],
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status": None,
            "url": url,
            "final_url": None,
            "content_type": "",
            "x_robots_tag": "",
            "text": "",
            "error": type(exc).__name__,
        }


def strip_html(value: str) -> str:
    text = TAG_RE.sub(" ", unescape(value or ""))
    return " ".join(text.split())


def words(value: str) -> int:
    return len(WORD_RE.findall(strip_html(value)))


def html_signals(page: dict) -> dict:
    html = page.get("text", "")
    lower = html.lower()
    meta_noindex = bool(
        re.search(
            r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'][^"\']*noindex',
            lower,
            re.I,
        )
        or re.search(
            r'<meta[^>]+content=["\'][^"\']*noindex[^"\']*["\'][^>]+name=["\']robots["\']',
            lower,
            re.I,
        )
    )
    pub_ids = sorted(set(PUB_RE.findall(html)))
    return {
        "meta_noindex": meta_noindex,
        "x_robots_noindex": "noindex" in (page.get("x_robots_tag") or "").lower(),
        "adsense_script": "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" in lower,
        "adsense_meta": "google-adsense-account" in lower,
        "platform_meta": "google-adsense-platform-account" in lower,
        "data_ad_host": "data-ad-host" in lower,
        "iubenda": "iubenda" in lower,
        "chi_sono_link": "/chi-sono" in lower,
        "privacy_link": "privacy" in lower,
        "publisher_ids": pub_ids,
        "visible_word_estimate": words(html),
    }


def robots_signals(text: str) -> dict:
    cleaned = []
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            cleaned.append(line)
    groups = {}
    agents = []
    for line in cleaned:
        if ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        key_l = key.lower()
        if key_l == "user-agent":
            agents = [value.lower()]
            groups.setdefault(value.lower(), [])
        elif key_l == "disallow":
            for agent in agents:
                groups.setdefault(agent, []).append(value)
    explicit = {}
    for agent in ("mediapartners-google", "google-display-ads-bot", "*"):
        rules = groups.get(agent, [])
        explicit[agent] = {
            "rules": rules,
            "root_blocked": any(rule.strip() == "/" for rule in rules),
        }
    return {"groups": explicit, "raw": text[:12000]}


def wp_inventory() -> dict:
    endpoint = urljoin(BASE_URL + "/", "wp-json/wp/v2/posts")
    result = {
        "reachable": False,
        "published_posts_seen": 0,
        "total_published_header": None,
        "under_200_words": 0,
        "under_400_words": 0,
        "at_least_400_words": 0,
        "latest_posts": [],
    }
    try:
        r = requests.get(
            endpoint,
            params={
                "per_page": 100,
                "page": 1,
                "status": "publish",
                "_fields": "id,date,link,title,content,excerpt",
            },
            headers={"User-Agent": UA_BROWSER},
            timeout=TIMEOUT,
        )
        result["status"] = r.status_code
        if r.status_code != 200:
            return result
        data = r.json()
        if not isinstance(data, list):
            return result
        result["reachable"] = True
        total = r.headers.get("X-WP-Total")
        result["total_published_header"] = int(total) if str(total).isdigit() else None
        result["published_posts_seen"] = len(data)
        for post in data:
            body = ((post.get("content") or {}).get("rendered") or "")
            wc = words(body)
            if wc < 200:
                result["under_200_words"] += 1
            if wc < 400:
                result["under_400_words"] += 1
            else:
                result["at_least_400_words"] += 1
            if len(result["latest_posts"]) < 12:
                result["latest_posts"].append({
                    "date": post.get("date"),
                    "title": strip_html((post.get("title") or {}).get("rendered") or ""),
                    "word_count": wc,
                    "link": post.get("link"),
                })
        return result
    except (requests.RequestException, ValueError, TypeError):
        return result


def summarize(report: dict) -> list[str]:
    issues = []
    home = report["pages"]["home"]
    hs = home.get("signals", {})
    if home.get("status") != 200:
        issues.append("CRITICO: homepage non restituisce HTTP 200.")
    if hs.get("meta_noindex") or hs.get("x_robots_noindex"):
        issues.append("CRITICO: homepage contiene un segnale noindex.")
    if not (hs.get("adsense_script") or hs.get("adsense_meta") or report["ads_txt"].get("google_lines")):
        issues.append("CRITICO: non rilevato alcun metodo pubblico di collegamento AdSense.")
    robots = report["robots"].get("signals", {}).get("groups", {})
    for agent in ("mediapartners-google", "google-display-ads-bot"):
        if robots.get(agent, {}).get("root_blocked"):
            issues.append(f"CRITICO: robots.txt blocca {agent} alla radice.")
    if report["pages"]["chi_sono"].get("status") != 200:
        issues.append("ALTO: pagina Chi sono non raggiungibile con HTTP 200.")
    if not hs.get("chi_sono_link"):
        issues.append("ALTO: link a Chi sono non rilevato nella homepage.")
    if not hs.get("privacy_link"):
        issues.append("ALTO: link privacy non rilevato nella homepage.")
    if not hs.get("iubenda"):
        issues.append("MEDIO: script/riferimenti Iubenda non rilevati nell'HTML statico della homepage.")
    if not report["sitemap"].get("available"):
        issues.append("MEDIO: nessuna sitemap standard rilevata.")
    inv = report["wordpress_inventory"]
    if inv.get("reachable"):
        total = inv.get("total_published_header")
        if isinstance(total, int) and total < 15:
            issues.append(f"MEDIO: archivio WordPress ridotto ({total} articoli pubblicati).")
        if inv.get("under_200_words", 0):
            issues.append(
                f"MEDIO: {inv['under_200_words']} degli ultimi {inv['published_posts_seen']} articoli sono sotto 200 parole."
            )
    else:
        issues.append("INFO: API REST WordPress non leggibile pubblicamente; inventario non verificato.")
    if not issues:
        issues.append("NESSUN BLOCCO TECNICO EVIDENTE rilevato dall'audit automatico.")
    return issues


def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "pages": {},
    }
    checks = {
        "home": "/",
        "chi_sono": "/chi-sono/",
    }
    for name, path in checks.items():
        page = get(path)
        report["pages"][name] = {
            k: v for k, v in page.items() if k != "text"
        }
        if page.get("status") == 200 and "html" in page.get("content_type", "").lower():
            report["pages"][name]["signals"] = html_signals(page)
        else:
            report["pages"][name]["signals"] = {}

    # Confronta accesso homepage con i due user-agent AdSense.
    report["crawler_access"] = {}
    for label, ua in (("mediapartners", UA_MEDIA), ("display_ads_bot", UA_DISPLAY)):
        page = get("/", ua)
        report["crawler_access"][label] = {
            "status": page.get("status"),
            "final_url": page.get("final_url"),
            "content_type": page.get("content_type"),
            "error": page.get("error"),
        }

    robots = get("/robots.txt")
    report["robots"] = {
        "status": robots.get("status"),
        "final_url": robots.get("final_url"),
        "signals": robots_signals(robots.get("text", "")) if robots.get("status") == 200 else {},
    }

    ads = get("/ads.txt")
    ads_lines = []
    if ads.get("status") == 200:
        for raw in ads.get("text", "").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and line.lower().startswith("google.com,"):
                ads_lines.append(line)
    report["ads_txt"] = {
        "status": ads.get("status"),
        "final_url": ads.get("final_url"),
        "google_lines": ads_lines[:30],
        "publisher_ids": sorted(set(PUB_RE.findall("\n".join(ads_lines)))),
    }

    sitemap_candidates = []
    for path in ("/sitemap_index.xml", "/wp-sitemap.xml"):
        page = get(path)
        sitemap_candidates.append({
            "path": path,
            "status": page.get("status"),
            "final_url": page.get("final_url"),
            "looks_xml": (
                page.get("status") == 200
                and ("xml" in page.get("content_type", "").lower() or "<urlset" in page.get("text", "").lower() or "<sitemapindex" in page.get("text", "").lower())
            ),
        })
    report["sitemap"] = {
        "available": any(x["looks_xml"] for x in sitemap_candidates),
        "candidates": sitemap_candidates,
    }

    # Alcune installazioni Iubenda espongono la policy con slug diverso:
    # il link privacy in homepage resta il segnale principale.
    report["wordpress_inventory"] = wp_inventory()
    report["summary"] = summarize(report)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("AI VISION - AUDIT TECNICO ADSENSE")
    print("=" * 72)
    print("Sito:", BASE_URL)
    print("Homepage:", report["pages"]["home"].get("status"))
    print("Crawler Mediapartners-Google:", report["crawler_access"]["mediapartners"].get("status"))
    print("Crawler Google-Display-Ads-Bot:", report["crawler_access"]["display_ads_bot"].get("status"))
    print("robots.txt:", report["robots"].get("status"))
    print("ads.txt:", report["ads_txt"].get("status"), "- righe Google:", len(ads_lines))
    print("Sitemap disponibile:", report["sitemap"]["available"])
    inv = report["wordpress_inventory"]
    print("WordPress REST:", "OK" if inv.get("reachable") else "non verificabile")
    print("Articoli pubblicati (header WP):", inv.get("total_published_header"))
    print("-" * 72)
    for item in report["summary"]:
        print(item)
    print("Report:", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
