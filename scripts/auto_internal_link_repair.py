#!/usr/bin/env python3
"""Aggiunge collegamenti interni solo quando la similarità tematica supera soglie conservative."""
from __future__ import annotations
import argparse, collections, datetime as dt, html, json, math, os, re, unicodedata
from pathlib import Path
import requests
from urllib.parse import urlsplit

BASE = "https://aivision.altervista.org"
PLAN = Path("data/auto_internal_links_plan.json")
BACKUP = Path("data/auto_internal_links_backup.json")
RESULT = Path("data/auto_internal_links_result.json")
MARKER = "<!-- ai-vision-auto-related-links:v1 -->"
MAX_UPDATES = 120
PER_PAGE = 100
MIN_SCORE = 0.18
SECOND_SCORE = 0.20

STOP = set("""a ad al allo alla ai agli alle anche ancora avere aveva avevano avendo avrai avrà avranno
che chi ci cioè come con contro cui da dal dallo dalla dai dagli dalle dentro dopo dove due e ed
era erano essere fa fra fra gli ha hai hanno il in io la le lei li lo loro lui ma me mentre mi
molto nei nel nella nelle no noi non o od oggi ogni oltre per perché più quale quali quando quanto
quanta quanti quante quello quella quelli quelle questo questa questi queste qui quindi se sei senza
si sia siano siamo siete sono su sul sullo sulla sui sugli sulle tra tre tu un una uno vi voi
the and or for of in on to by as at from is are was were be been being this that these those it
its their they them you your we our can will may might has have had about into over under than
offerta offerte promozione promozioni prezzo prezzi sconto sconti amazon euro novita nuovo nuova
nuovi nuove articolo scopri caratteristiche specifiche recensione recensioni disponibile disponibili
2024 2025 2026 2027 oggi guida come tutto cosa quali quale quando""".split())

def plain(value: str) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return " ".join(value.split())

def tokenize(value: str) -> list[str]:
    value = unicodedata.normalize("NFKD", (value or "").lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return [w for w in re.findall(r"[a-z0-9]{2,}", value) if w not in STOP and not w.isdigit()]

def fetch_all(session: requests.Session) -> list[dict]:
    posts, page = [], 1
    while True:
        response = session.get(f"{BASE}/wp-json/wp/v2/posts", params={
            "status": "publish", "context": "edit", "per_page": PER_PAGE, "page": page,
            "orderby": "id", "order": "asc",
            "_fields": "id,status,slug,link,title,content,categories,modified,date"
        }, timeout=(8, 40))
        if response.status_code == 400 and page > 1:
            break
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        posts.extend(batch)
        if len(batch) < PER_PAGE:
            break
        page += 1
        if page > 20:
            raise RuntimeError("Paginazione WordPress oltre il limite di sicurezza.")
    return posts

def valid_internal_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return parsed.scheme == "https" and parsed.netloc == "aivision.altervista.org" and not parsed.query and not parsed.fragment
    except Exception:
        return False

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "apply"])
    mode = parser.parse_args().mode
    base = os.getenv("WP_BASE_URL", "").rstrip("/").removesuffix("/wp-json")
    user = os.getenv("WP_USERNAME", "")
    password = os.getenv("WP_APP_PASSWORD", "")
    if base != BASE or not user or not password:
        raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    session = requests.Session()
    session.auth = (user, password)
    session.headers["User-Agent"] = "AIVision-Auto-Internal-Link-Repair/1.0"

    def read(post_id: int) -> dict:
        response = session.get(f"{BASE}/wp-json/wp/v2/posts/{post_id}",
                               params={"context": "edit"}, timeout=(8, 35))
        response.raise_for_status()
        return response.json()

    if mode == "prepare":
        posts = fetch_all(session)
        docs, titles, categories, raw_contents = {}, {}, {}, {}
        for post in posts:
            pid = int(post["id"])
            title = plain((post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered") or "")
            raw = (post.get("content") or {}).get("raw")
            if not isinstance(raw, str):
                continue
            text = plain(raw)
            docs[pid] = tokenize(title + " " + text[:4500])
            titles[pid] = title
            categories[pid] = set(post.get("categories") or [])
            raw_contents[pid] = raw

        n = len(docs)
        document_frequency = collections.Counter(token for tokens in docs.values() for token in set(tokens))
        idf = {token: math.log((n + 1) / (count + 1)) + 1 for token, count in document_frequency.items()}
        vectors, norms = {}, {}
        for pid, tokens in docs.items():
            counts = collections.Counter(tokens)
            vector = {token: count * idf.get(token, 1.0) for token, count in counts.items()}
            vectors[pid] = vector
            norms[pid] = math.sqrt(sum(value * value for value in vector.values()))

        def cosine(a: int, b: int) -> float:
            va, vb = vectors[a], vectors[b]
            denom = norms[a] * norms[b]
            if not denom:
                return 0.0
            return sum(value * vb.get(token, 0.0) for token, value in va.items()) / denom

        by_id = {int(p["id"]): p for p in posts if int(p["id"]) in docs}
        rows, skipped = [], []
        for pid, post in by_id.items():
            raw = raw_contents[pid]
            if re.search(r'href\s*=\s*["\'](?:https?://aivision\.altervista\.org|/)', raw, re.I):
                continue
            if MARKER in raw:
                continue
            title_tokens = set(tokenize(titles[pid]))
            candidates = []
            for candidate_id, candidate in by_id.items():
                if candidate_id == pid:
                    continue
                shared = set(docs[pid]) & set(docs[candidate_id])
                rare_shared = {token for token in shared if idf.get(token, 1.0) >= 1.8}
                shared_title = title_tokens & set(docs[candidate_id])
                if len(rare_shared) < 2 or not shared_title:
                    continue
                score = cosine(pid, candidate_id)
                category_overlap = categories[pid] & categories[candidate_id]
                if category_overlap:
                    score += 0.025
                if score < MIN_SCORE:
                    continue
                url = str(candidate.get("link") or "")
                if not valid_internal_url(url):
                    continue
                candidates.append((score, candidate_id, url, titles[candidate_id], sorted(rare_shared)[:8]))
            candidates.sort(reverse=True, key=lambda item: item[0])
            selected = []
            for candidate in candidates:
                if len(selected) == 0 and candidate[0] >= MIN_SCORE:
                    selected.append(candidate)
                elif len(selected) == 1 and candidate[0] >= SECOND_SCORE:
                    if candidate[1] != selected[0][1]:
                        selected.append(candidate)
                if len(selected) >= 2:
                    break
            if not selected:
                skipped.append({"id": pid, "title": titles[pid], "reason": "nessun collegamento abbastanza pertinente"})
                continue
            links_html = " · ".join(
                f'<a href="{url}">{html.escape(candidate_title)}</a>'
                for score, candidate_id, url, candidate_title, shared in selected
            )
            after = raw.rstrip() + "\n\n" + MARKER + f'\n<p class="av-related-links"><strong>Approfondimenti:</strong> {links_html}.</p>'
            rows.append({
                "id": pid, "slug": post.get("slug"), "modified": post.get("modified"),
                "title": titles[pid], "before": raw, "after": after,
                "links": [{"id": cid, "url": url, "title": t, "score": round(score, 4), "shared_terms": terms}
                          for score, cid, url, t, terms in selected]
            })
            if len(rows) >= MAX_UPDATES:
                break
        payload = {"site": BASE, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "inventory": len(posts), "targeted": len(rows), "skipped": skipped, "changes": rows}
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        BACKUP.write_text(json.dumps({
            "site": BASE, "created_at": payload["created_at"],
            "posts": [{"id": row["id"], "slug": row["slug"], "modified": row["modified"],
                       "title": row["title"], "content_raw": row["before"], "links": row["links"]}
                      for row in rows]
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Articoli pubblicati:", len(posts))
        print("Articoli con link interni pianificati:", len(rows))
        print("Articoli senza candidato sufficientemente pertinente:", len(skipped))
        return 0

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("site") != BASE or not isinstance(plan.get("changes"), list) or len(plan["changes"]) > MAX_UPDATES:
        raise RuntimeError("Piano interno non valido.")
    results, errors = [], []
    for row in plan["changes"]:
        try:
            live = read(row["id"])
            live_raw = (live.get("content") or {}).get("raw")
            live_title = (live.get("title") or {}).get("raw") or (live.get("title") or {}).get("rendered")
            if (live.get("status") != "publish" or live.get("slug") != row["slug"]
                    or live.get("modified") != row["modified"] or live_raw != row["before"]
                    or live_title != row["title"]):
                raise RuntimeError("Articolo modificato dopo il backup; salto per evitare sovrascritture.")
            response = session.post(f"{BASE}/wp-json/wp/v2/posts/{row['id']}",
                                    params={"context": "edit"}, json={"content": row["after"]},
                                    timeout=(8, 45), allow_redirects=False)
            response.raise_for_status()
            saved = read(row["id"])
            if (saved.get("content") or {}).get("raw") != row["after"]:
                raise RuntimeError("Verifica del contenuto fallita.")
            results.append({"id": row["id"], "slug": row["slug"], "status": "updated_and_verified",
                            "links": row["links"]})
            print(f"Post {row['id']}: {len(row['links'])} link interni verificati.")
        except Exception as exc:
            errors.append({"id": row["id"], "status": "error", "error": str(exc)})
            print(f"Post {row['id']}: ERRORE: {exc}")
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps({"completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                  "updated": len(results), "errors": errors, "results": results},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print("Aggiornati:", len(results), "errori:", len(errors))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
