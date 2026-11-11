#!/usr/bin/env python3
"""Inventario mirato e unica correzione editoriale certa per AI Vision.

Aggiorna il titolo Zelda soltanto se il post pubblicato corrisponde esattamente
al titolo con il refuso noto. Tutto il resto è diagnostico/read-only.
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

BASE = "https://aivision.altervista.org"
OUT = Path("data/targeted_wp_review.json")
ZELDA_SLUG = "zelda-ocarina-of-time-remake-code-negozi-fisico"
ZELDA_OLD = "Zelda Ocarina of Time Remake: file oceaniche per il fisco"
ZELDA_NEW = "Zelda Ocarina of Time Remake: file oceaniche per il fisico"
ARTICLE_SLUGS = [
    "soundpeats-cove-pro-offerta-aliexpress",
    "gta-6-sondaggio-record-previsioni-vendita",
    ZELDA_SLUG,
    "oppo-find-x10-e-pro-max-sconto-store-ufficiale",
]
MISSING_SLUGS = [
    "robot-umanoidi-in-casa-entro-il-2027-fantascienza-o-realta-imminente",
    "upscaling-8k-ridai-vita-alle-tue-vecchie-foto-sfocate-in-un-click",
    "addio-slop-perche-il-2026-sara-lanno-dellia-di-qualita-finalmente",
    "cena-stellata-con-un-click-come-lia-sta-rivoluzionando-la-tua-spesa",
]
TAG_SLUGS = ["bluetti", "tv", "bluetooth", "kernel", "element-pro"]
CATEGORY_SLUGS = ["ai-life-hacks", "fotografia-ia"]

def plain(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())

def words(s):
    return len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ]+(?:['’][\wÀ-ÖØ-öø-ÿ]+)*\b", plain(s)))

def main():
    user, password = os.getenv("WP_USERNAME", ""), os.getenv("WP_APP_PASSWORD", "")
    base = os.getenv("WP_BASE_URL", "").rstrip("/").removesuffix("/wp-json")
    if base != BASE or not user or not password:
        raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    s = requests.Session()
    s.auth = (user, password)
    s.headers["User-Agent"] = "AIVision-Targeted-Repair/1.0"
    def get(path, params=None):
        r = s.get(urljoin(BASE + "/", "wp-json/wp/v2/" + path.lstrip("/")),
                  params=params or {}, timeout=(8, 30))
        r.raise_for_status()
        return r.json()
    def post(path, payload):
        r = s.post(urljoin(BASE + "/", "wp-json/wp/v2/" + path.lstrip("/")),
                   json=payload, timeout=(8, 30), allow_redirects=False)
        r.raise_for_status()
        return r.json()

    result = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "site": BASE, "mode": "safe_exact_title_fix_plus_readonly_inventory",
              "title_fix": {}, "articles": [], "missing_slug_lookup": [],
              "tags": [], "categories": [], "errors": []}

    # Fix only the exact, known typographical error; preserve the existing slug.
    try:
        rows = get("posts", {"slug": ZELDA_SLUG, "context": "edit", "_fields": "id,slug,status,title,link,modified"})
        if len(rows) == 1 and rows[0].get("status") == "publish":
            p = rows[0]
            current = plain((p.get("title") or {}).get("rendered") or "")
            if current == ZELDA_OLD:
                backup = {"id": p["id"], "slug": p["slug"], "old_title": current,
                          "old_modified": p.get("modified"), "url": p.get("link")}
                # Re-read immediately before writing; no content/slug/SEO fields touched.
                latest = get(f"posts/{p['id']}", {"context": "edit", "_fields": "id,slug,status,title,modified"})
                latest_title = plain((latest.get("title") or {}).get("raw") or
                                     (latest.get("title") or {}).get("rendered") or "")
                if (latest.get("status") == "publish" and latest.get("slug") == ZELDA_SLUG
                        and latest_title == ZELDA_OLD and latest.get("modified") == p.get("modified")):
                    saved = post(f"posts/{p['id']}", {"title": ZELDA_NEW})
                    saved_title = plain((saved.get("title") or {}).get("rendered") or "")
                    result["title_fix"] = {**backup, "new_title": saved_title,
                                           "status": "updated_and_verified" if saved_title == ZELDA_NEW else "verification_failed"}
                else:
                    result["title_fix"] = {"status": "skipped_changed_during_check"}
            else:
                result["title_fix"] = {"status": "not_exact_match_no_change", "current_title": current,
                                       "post_id": p.get("id")}
        else:
            result["title_fix"] = {"status": "not_found_or_not_unique", "matches": len(rows)}
    except Exception as e:
        result["title_fix"] = {"status": "error", "error": f"{type(e).__name__}: {str(e)[:180]}"}
        result["errors"].append(result["title_fix"])

    for slug in ARTICLE_SLUGS:
        try:
            rows = get("posts", {"slug": slug, "context": "edit",
                                 "_fields": "id,slug,status,title,link,modified,content,excerpt,categories,aivision_seo"})
            if len(rows) != 1:
                result["articles"].append({"slug": slug, "status": "not_unique", "matches": len(rows)})
                continue
            p = rows[0]
            body = (p.get("content") or {}).get("rendered") or ""
            result["articles"].append({
                "id": p.get("id"), "slug": slug, "status": p.get("status"),
                "title": plain((p.get("title") or {}).get("rendered") or ""),
                "url": p.get("link"), "modified": p.get("modified"),
                "words": words(body), "internal_links": len(re.findall(r'href="(?:https?://aivision\\.altervista\\.org)?/', body, re.I)),
                "categories": p.get("categories", []),
                "aivision_seo": p.get("aivision_seo", {}),
                "excerpt": plain((p.get("excerpt") or {}).get("rendered") or "")[:350],
                "body_text": plain(body)[:6500],
            })
        except Exception as e:
            result["errors"].append({"slug": slug, "error": f"{type(e).__name__}: {str(e)[:160]}"})

    # Ricerca di articoli affini per dispositivi audio/cuffie.
    try:
        rows = get("posts", {"search": "cuffie", "status": "publish", "per_page": 20,
            "orderby": "date", "order": "desc", "_fields": "id,date,slug,title,link,categories"})
        result["audio_link_candidates"] = [{"id": p.get("id"), "date": p.get("date"),
            "title": plain((p.get("title") or {}).get("rendered") or ""),
            "url": p.get("link")} for p in rows]
    except Exception as e:
        result["errors"].append({"audio_search": f"{type(e).__name__}: {str(e)[:160]}"})

    # Candidate interni realmente pubblicati nelle stesse categorie.
    for category_id in (79, 322):
        try:
            rows = get("posts", {"categories": category_id, "status": "publish",
                "per_page": 30, "orderby": "date", "order": "desc",
                "_fields": "id,date,slug,title,link,categories"})
            result.setdefault("internal_link_candidates", {})[str(category_id)] = [
                {"id": p.get("id"), "date": p.get("date"), "slug": p.get("slug"),
                 "title": plain((p.get("title") or {}).get("rendered") or ""),
                 "url": p.get("link")} for p in rows]
        except Exception as e:
            result["errors"].append({"category_posts": category_id,
                "error": f"{type(e).__name__}: {str(e)[:160]}"})

    for slug in MISSING_SLUGS:
        try:
            rows = get("posts", {"slug": slug, "context": "edit", "status": "any", "_fields": "id,slug,status,title,link"})
            result["missing_slug_lookup"].append({"slug": slug, "published_matches": len(rows),
                "matches": [{"id": p.get("id"), "status": p.get("status"),
                             "title": plain((p.get("title") or {}).get("rendered") or "")} for p in rows]})
        except Exception as e:
            result["errors"].append({"slug": slug, "error": f"{type(e).__name__}: {str(e)[:160]}"})

    for slug in TAG_SLUGS:
        try:
            rows = get("tags", {"slug": slug, "context": "edit", "_fields": "id,slug,name,count,link,meta"})
            if rows:
                term = rows[0]
                result["tags"].append({"id": term.get("id"), "slug": term.get("slug"), "name": term.get("name"), "count": term.get("count"), "meta": term.get("meta", {})})
            else:
                result["tags"].append({"slug": slug, "exists": False})
        except Exception as e:
            result["errors"].append({"tag": slug, "error": f"{type(e).__name__}: {str(e)[:160]}"})
    for slug in CATEGORY_SLUGS:
        try:
            rows = get("categories", {"slug": slug, "context": "edit", "_fields": "id,slug,name,count,link,meta"})
            if rows:
                term = rows[0]
                result["categories"].append({"id": term.get("id"), "slug": term.get("slug"), "name": term.get("name"), "count": term.get("count"), "meta": term.get("meta", {})})
            else:
                result["categories"].append({"slug": slug, "exists": False})
        except Exception as e:
            result["errors"].append({"category": slug, "error": f"{type(e).__name__}: {str(e)[:160]}"})

    # Espone le route Yoast registrate: serve a scegliere un metodo supportato
    # per noindex dei singoli tag, senza toccare impostazioni globali.
    try:
        root = s.get(BASE + "/wp-json/", timeout=(8, 20))
        root.raise_for_status()
        routes = root.json().get("routes", {})
        result["yoast_rest_routes"] = {
            path: {"methods": sorted(list((data.get("endpoints") or [{}])[0].get("methods", []))),
                   "args": sorted(list((data.get("endpoints") or [{}])[0].get("args", {}).keys()))}
            for path, data in routes.items() if "yoast" in path.lower()
        }
    except Exception as e:
        result["errors"].append({"yoast_rest_routes": f"{type(e).__name__}: {str(e)[:150]}"})

    # Identifica il motore SEO e le sue API prima di qualsiasi noindex tassonomico.
    try:
        root = get_root = s.get(BASE + "/wp-json/", timeout=(8, 20))
        root.raise_for_status()
        data = root.json()
        result["seo_rest_namespaces"] = [n for n in data.get("namespaces", [])
            if any(k in n.lower() for k in ("yoast", "rank", "aioseo", "seo"))]
    except Exception as e:
        result["errors"].append({"seo_rest_namespaces": f"{type(e).__name__}: {str(e)[:150]}"})
    try:
        abilities = s.get(BASE + "/wp-json/wp-abilities/v1/abilities",
                          params={"category": "yoast-seo"}, timeout=(8, 20))
        if abilities.status_code == 200:
            payload = abilities.json()
            items = payload if isinstance(payload, list) else payload.get("abilities", [])
            result["yoast_abilities"] = [x.get("name") for x in items if isinstance(x, dict)]
        else:
            result["yoast_abilities_status"] = abilities.status_code
    except Exception as e:
        result["errors"].append({"yoast_abilities": f"{type(e).__name__}: {str(e)[:150]}"})
    try:
        settings = s.get(BASE + "/wp-json/wp/v2/settings", params={"context":"edit"}, timeout=(8,20))
        if settings.status_code == 200 and isinstance(settings.json(), dict):
            result["yoast_setting_keys"] = [k for k in settings.json() if "yoast" in k.lower() or "wpseo" in k.lower()]
        else:
            result["yoast_settings_status"] = settings.status_code
    except Exception as e:
        result["errors"].append({"yoast_settings": f"{type(e).__name__}: {str(e)[:150]}"})

    try:
        home = s.get(BASE + "/tag/bluetti/", timeout=(8, 20))
        result["tag_html_markers"] = {
            "status": home.status_code,
            "seo_plugins": [name for name in ("yoast", "rank-math", "aioseo", "all-in-one-seo", "aivision_seo")
                            if name in home.text.lower()],
            "generator_tag_present": 'name="generator"' in home.text.lower(),
            "seo_title": __import__("re").findall(r'<title[^>]*>(.*?)</title>', home.text, re.I | re.S)[:1],
        }
    except Exception as e:
        result["errors"].append({"tag_html_markers": f"{type(e).__name__}: {str(e)[:150]}"})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"title_fix": result["title_fix"],
        "articles": [{k:v for k,v in x.items() if k not in ("excerpt",)} for x in result["articles"]],
        "missing_slug_lookup": result["missing_slug_lookup"], "tags": result["tags"],
        "categories": result["categories"], "errors": result["errors"]}, ensure_ascii=False, indent=2))
    if result["errors"] or result["title_fix"].get("status") == "verification_failed":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
