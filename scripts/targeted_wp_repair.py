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
    "sonos-beam-ultra-e-ace-ultra-arrivano-nei-negozi",
    "iphone-18-pro-recensione-novita",
    "the-witcher-3-wild-hunt-remastered-disponibile-oggi",
    "disponibile-ios-27-0-1-correzioni-novita",
    "xbox-disc-to-digital-disponibile-per-tutti-gli-utenti",
    "safari-funzione-avvisami-monitorare-prezzi",
    "eni-tagli-gas-luce-ottobre",
    "football-manager-27-data-di-uscita-e-versioni",
    "blender-su-android-tablet-2027",
    "tv-lg-nanocell-ai-75-offerta-amazon",
    "vulnerabilita-fortimail-attacchi-zero-day",
    "lg-ultragear-evo-gx9-recensione",
    "lego-playstation-1-prezzo-pezzi-accesso-anticipato",
    "recensione-iphone-18-pro-max",
    "samsung-galaxy-watch8-offerta-amazon",
    "giochi-in-uscita-ottobre-offerte",
    "pixel-10a-aumento-prezzo",
    "smart-tv-in-offerta-65-75-pollici",
    "sconto-dyson-coupon-100-euro",
    "crucial-p310-1tb-offerta-amazon",
    "e-bike-in-carbonio-engwe-n1-pro-air-doppio-sconto",
    "leapmotor-b03x-prova-prezzi-consumi",
    "dji-osmo-pocket-3-offerta-amazon",
    "leapmotor-b03x",
    "gta-6-copie-fisiche-esaurite",
    "call-of-duty-modern-warfare-4-sconto-nintendo-switch-2",
    "mycopunk-analisi-co-op-shooter",
    "gemini-su-apple-carplay-google-maps",
    "xbox-nano-controller-pad-tascabile-microsoft",
    "dreame-airstyle-pro-2-recensione-prezzo",
    "anker-maggo-power-bank-2-pro",
    "anker-maggo-power-bank-2-pro-recensione-caratteristiche",
    "festa-delle-offerte-prime-sconti-tecnologia",
    "festa-offerte-prime-ultime-ore-sconti-tech",
    "gta-vi-xbox-cloud-gaming-senza-pc",
    "gta-6-xbox-cloud-gaming-xbox-one",
    "netflix-aumenta-prezzi-italia-nuovo-listino",
    "aumenti-prezzi-netflix-italia-nuove-tariffe",
    "apple-home-collection-smart-home-lg-schneider",
    "apple-home-collection-accessori-smart-home",
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

    # Legge tramite Yoast Abilities i campi SEO effettivamente gestiti da Yoast.
    # Sola lettura: distingue il bridge AIVision dai metadati Yoast pubblicati.
    try:
        registry = s.get(BASE + "/wp-json/wp-abilities/v1/abilities",
                         params={"category": "yoast-seo"}, timeout=(8, 20))
        registry.raise_for_status()
        registry_data = registry.json()
        ability_items = registry_data if isinstance(registry_data, list) else registry_data.get("abilities", [])
        result["yoast_ability_schemas"] = {
            item.get("name"): item.get("input_schema")
            for item in ability_items if isinstance(item, dict)
            and item.get("name") in ("yoast-seo/get-post-seo-data", "yoast-seo/update-post-seo-data")
        }
        result["yoast_post_seo_data"] = []
        for post_id in (465, 478):
            response = s.get(
                BASE + "/wp-json/wp-abilities/v1/abilities/yoast-seo/get-post-seo-data/run",
                params={"input[post_id]": str(post_id)},
                timeout=(8, 25), allow_redirects=False
            )
            entry = {"post_id": post_id, "http_status": response.status_code}
            try:
                entry["response"] = response.json()
            except ValueError:
                entry["response_text"] = response.text[:500]
            result["yoast_post_seo_data"].append(entry)
    except Exception as e:
        result["errors"].append({"yoast_post_seo_data": f"{type(e).__name__}: {str(e)[:180]}"})

    # Confronta l'HTML pubblico con l'output Yoast REST per le due pagine
    # segnalate senza meta description: individua anche eventuali tag duplicati.
    try:
        result["live_meta_diagnostics"] = []
        for page_url in (
            BASE + "/sonos-beam-ultra-e-ace-ultra-arrivano-nei-negozi/",
            BASE + "/iphone-18-pro-recensione-novita/",
        ):
            page = s.get(page_url, timeout=(8, 25), allow_redirects=True)
            tags = re.findall(r"<meta\b[^>]*>", page.text, re.I)
            descriptions = [tag for tag in tags if re.search(r"\bname\s*=\s*['\\"]description['\\"]", tag, re.I)]
            og_descriptions = [tag for tag in tags if re.search(r"\bproperty\s*=\s*['\\"]og:description['\\"]", tag, re.I)]
            head = s.get(BASE + "/wp-json/yoast/v1/get_head",
                         params={"url": page_url}, timeout=(8, 25))
            head_data = head.json() if head.status_code == 200 else {"http_status": head.status_code}
            result["live_meta_diagnostics"].append({
                "url": page_url, "page_status": page.status_code,
                "description_meta_tags": descriptions, "og_description_meta_tags": og_descriptions,
                "yoast_head_status": head.status_code,
                "yoast_head": head_data if isinstance(head_data, dict) else str(head_data)[:1200],
            })
    except Exception as e:
        result["errors"].append({"live_meta_diagnostics": f"{type(e).__name__}: {str(e)[:180]}"})

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

    # Mappa i post associati ai tag dopo aver caricato i termini.
    # Mappa ogni tag sottile agli articoli che lo utilizzano, per decidere la pulizia.
    for term in result.get("tags", []):
        if not term.get("id"):
            continue
        try:
            rows = get("posts", {"tags": term["id"], "status": "publish", "per_page": 20,
                "_fields": "id,date,slug,title,link,categories"})
            term["posts"] = [{"id": p.get("id"), "slug": p.get("slug"),
                "title": plain((p.get("title") or {}).get("rendered") or ""),
                "url": p.get("link")} for p in rows]
        except Exception as e:
            result["errors"].append({"tag_posts": term.get("slug"),
                "error": f"{type(e).__name__}: {str(e)[:150]}"})

    # Verifica in sola lettura se l'application password consente l'accesso alla
    # schermata amministrativa Yoast per un singolo tag (nessuna richiesta di scrittura).
    try:
        admin = s.get(BASE + "/wp-admin/term.php",
            params={"taxonomy": "post_tag", "tag_ID": 217, "post_type": "post"},
            timeout=(8, 20), allow_redirects=True)
        page = admin.text.lower()
        result["wp_admin_term_access"] = {
            "status": admin.status_code,
            "final_path": urljoin(BASE, admin.url).split(BASE, 1)[-1][:180],
            "is_login_page": "wp-login.php" in admin.url or "user_login" in page,
            "yoast_noindex_field_present": "wpseo_noindex" in page,
            "wp_nonce_present": "_wpnonce" in page,
            "admin_bar_present": "wpadminbar" in page
        }
    except Exception as e:
        result["errors"].append({"wp_admin_term_access": f"{type(e).__name__}: {str(e)[:150]}"})

    # Espone le route Yoast registrate: serve a scegliere un metodo supportato
    # per noindex dei singoli tag, senza toccare impostazioni globali.
    try:
        root = s.get(BASE + "/wp-json/", timeout=(8, 20))
        root.raise_for_status()
        routes = root.json().get("routes", {})
        result["yoast_routes_collection_type"] = type(routes).__name__
        if isinstance(routes, dict):
            result["yoast_rest_routes"] = {
                path: (data.get("endpoints") or [])[:2]
                for path, data in routes.items() if "yoast" in path.lower()
            }
        else:
            result["yoast_rest_routes"] = []
            result["yoast_routes_preview"] = routes[:30] if isinstance(routes, list) else str(routes)[:500]
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
