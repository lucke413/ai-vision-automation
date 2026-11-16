#!/usr/bin/env python3
"""Rende esplicitamente storici i titoli delle promozioni concluse, senza toccare URL o corpo."""
from __future__ import annotations
import argparse, datetime as dt, json, os
from pathlib import Path
import requests

BASE = "https://aivision.altervista.org"
PLAN = Path("data/historical_offer_titles_plan.json")
BACKUP = Path("data/historical_offer_titles_backup.json")
RESULT = Path("data/historical_offer_titles_result.json")
NOTICE_MARKER = 'class="av-price-status-note"'
FOCUS_KEYPHRASES = {
    1011: "coupon eBay 20%",
    1018: "Seagate FireCuda X Vault 8TB",
    1091: "Sony DualSense PlayStation Store",
    1117: "Google Pixel Flex",
    1131: "Return to Monkey Island",
    1148: "Corsair NIGHTSABRE Wireless",
    1157: "Xiaomi Redmi Note 15 Pro 5G",
}
UPDATES = {int(row[0]): {"slug": row[1], "title": row[2]} for row in json.loads("[[499,\"anker-prime-100w-offerta-39-99-euro\",\"Anker Prime 100W: caratteristiche e prezzo della promozione di settembre 2026\"],[548,\"dji-osmo-pocket-3-offerta-amazon\",\"DJI Osmo Pocket 3: caratteristiche e prezzo della promozione Amazon di ottobre 2026\"],[563,\"crucial-p310-1tb-offerta-amazon\",\"Crucial P310 1TB: specifiche e prezzo della promozione Amazon di ottobre 2026\"],[575,\"tcl-98t8d-offerta-minimo-storico\",\"TCL 98T8D da 98 pollici: caratteristiche e prezzo rilevato a ottobre 2026\"],[578,\"sconto-dyson-coupon-100-euro\",\"Dyson: come funzionava il codice promozionale da 100 euro di ottobre 2026\"],[581,\"e-bike-in-carbonio-engwe-n1-pro-air-doppio-sconto\",\"ENGWE N1 Pro e N1 Air: differenze e prezzo della promozione di ottobre 2026\"],[587,\"smart-tv-in-offerta-65-75-pollici\",\"Smart TV 65 e 75 pollici: modelli e prezzi delle promozioni di ottobre 2026\"],[605,\"bluetti-elite-30-v2-pannello-solare-offerta\",\"BLUETTI Elite 30 V2: caratteristiche e prezzo della promozione di ottobre 2026\"],[614,\"telecamera-reolink-4k-offerta-amazon\",\"Telecamera Reolink 4K: caratteristiche e prezzo della promozione Amazon di ottobre 2026\"],[620,\"silent-hill-f-xbox-series-x-offerta-amazon\",\"Silent Hill f Day One Edition: prezzo e promozione Amazon di ottobre 2026\"],[648,\"braun-sensian-7-offerta-amazon\",\"Braun Sensian 7: caratteristiche e prezzo della promozione Amazon di ottobre 2026\"],[657,\"ecoflow-stream-ac-pro-offerta-minimo-storico\",\"EcoFlow STREAM AC Pro: caratteristiche e prezzo della promozione di ottobre 2026\"],[663,\"ringconn-gen-2-air-offerta-amazon\",\"RingConn Gen 2 Air: caratteristiche e prezzo della promozione di ottobre 2026\"],[675,\"kindle-in-offerta-base-colorsoft\",\"Kindle e Kindle Colorsoft: modelli e prezzi delle promozioni di ottobre 2026\"],[684,\"samsung-galaxy-a-in-offerta\",\"Samsung Galaxy A27, A37 e A57: prezzi rilevati nelle promozioni di ottobre 2026\"],[690,\"offerte-prime-anticipate-lg-oled-b6e-g5\",\"LG OLED B6E e OLED evo G5: prezzi delle offerte Prime di ottobre 2026\"],[706,\"monitor-aoc-ag276qzd2am-offerta-amazon\",\"AOC AG276QZD2AM: caratteristiche e prezzo rilevato a ottobre 2026\"],[735,\"festa-delle-offerte-prime-sconti-tecnologia\",\"Festa delle Offerte Prime 2026: riepilogo dei prezzi tech di ottobre\"],[747,\"notebook-asus-v16-offerta-prime\",\"ASUS V16 con RTX 4050: caratteristiche e prezzo della promozione Prime di ottobre 2026\"],[768,\"amazon-seconda-mano-sconto-15-percento\",\"Amazon Seconda Mano: come funzionava la promozione del 15% di ottobre 2026\"],[780,\"samsung-galaxy-z-flip-8-offerta-amazon\",\"Samsung Galaxy Z Flip 8: caratteristiche e prezzo della promozione Amazon di ottobre 2026\"],[798,\"oura-ring-4-in-offerta-al-prezzo-piu-basso-di-sempre\",\"Oura Ring 4: caratteristiche e prezzo della promozione di ottobre 2026\"],[801,\"asus-prime-radeon-rx-9070-offerta\",\"ASUS PRIME Radeon RX 9070: caratteristiche e prezzo rilevato a ottobre 2026\"],[822,\"xiaomi-redmi-17-offerta-prezzo-batteria\",\"Xiaomi Redmi 17: caratteristiche e prezzo della promozione di ottobre 2026\"],[843,\"google-pixel-9a-offerta-caricatore-amazon\",\"Google Pixel 9a: prezzo rilevato e accessori inclusi nella promozione di ottobre 2026\"],[855,\"power-bank-cellularline-offerta\",\"Cellularline Power Bank 20.000 mAh: prezzo della promozione di ottobre 2026\"],[864,\"corsair-skiff-100-plus-offerta-amazon-minimo-storico\",\"Corsair Skiff 100 Plus: caratteristiche e prezzo della promozione Amazon di ottobre 2026\"],[876,\"iphone-17-con-promotion-offerta\",\"iPhone 17 con ProMotion: caratteristiche e prezzo rilevato a ottobre 2026\"],[894,\"marshall-emberton-iii-offerta-minimo-storico\",\"Marshall Emberton III: autonomia e prezzo della promozione di ottobre 2026\"],[903,\"logitech-mx-ergo-s-offerta-minimo-storico\",\"Logitech MX Ergo S: caratteristiche e prezzo della promozione di ottobre 2026\"],[915,\"asus-vivobook-15-offerta-amazon\",\"ASUS Vivobook 15: caratteristiche e prezzo della promozione Amazon di ottobre 2026\"],[924,\"kit-ring-con-videocitofono-e-videocamera-offerta\",\"Kit Ring con videocitofono e videocamera: prezzo della promozione Amazon di ottobre 2026\"],[931,\"blink-2k-offerta-videocitofono-cablato\",\"Blink 2K+: caratteristiche e prezzo della promozione di ottobre 2026\"],[940,\"soundpeats-cove-pro-offerta-aliexpress\",\"SoundPEATS Cove Pro: caratteristiche e prezzo della promozione AliExpress di ottobre 2026\"],[979,\"oral-b-io-3-offerta-amazon-prezzo\",\"Oral-B iO 3: prezzi delle promozioni Amazon di ottobre 2026\"],[1011,\"ebay-coupon-20-risparmio-300-euro\",\"eBay: come funzionava il coupon del 20% nell'ottobre 2026\"],[1018,\"seagate-firecuda-x-vault-8tb-offerta\",\"Seagate FireCuda X Vault 8TB: caratteristiche e prezzo della promozione di ottobre 2026\"],[1091,\"sony-dualsense-credito-playstation-store-offerta\",\"Sony DualSense e credito PlayStation Store: prezzi delle promozioni Amazon di ottobre 2026\"],[1117,\"google-pixel-flex-offerta-amazon\",\"Google Pixel Flex: caratteristiche e prezzo della promozione di ottobre 2026\"],[1131,\"return-to-monkey-island-offerta-instant-gaming\",\"Return to Monkey Island: prezzo della promozione Instant Gaming di ottobre 2026\"],[1148,\"corsair-nightsabre-wireless-offerta-amazon\",\"Corsair NIGHTSABRE Wireless: caratteristiche e prezzo della promozione di ottobre 2026\"],[1157,\"xiaomi-redmi-note-15-pro-5g-offerta-amazon\",\"Xiaomi Redmi Note 15 Pro 5G da 512 GB: prezzo della promozione Amazon di ottobre 2026\"],[1167,\"ugreen-revodok-pro-109-offerta-39-59-euro\",\"UGREEN Revodok Pro 109: caratteristiche e prezzo della promozione di ottobre 2026\"],[1170,\"lg-mini-rgb-da-65-pollici-offerta-amazon\",\"LG Mini RGB da 65 pollici: caratteristiche e prezzo della promozione Amazon di ottobre 2026\"],[1183,\"xiaomi-17t-pro-offerta-ebay-629-euro\",\"Xiaomi 17T Pro: prezzo della promozione eBay di ottobre 2026\"],[1201,\"sony-inzone-h9-ii-offerta-minimo-storico-amazon\",\"Sony INZONE H9 II: caratteristiche e prezzo della promozione Amazon di ottobre 2026\"],[1218,\"msi-mag-pano-m100l-sconto-amazon\",\"MSI MAG Pano M100L: caratteristiche e prezzo della promozione Amazon di ottobre 2026\"],[1221,\"gygabite-b850-aourus-elite-offerta-minimo-storico\",\"Gigabyte B850 AORUS ELITE: caratteristiche e prezzo della promozione Amazon di ottobre 2026\"],[1224,\"lg-nano-98-pollici-offerta-mediaworld\",\"LG Nano da 98 pollici: prezzo della promozione MediaWorld di ottobre 2026\"],[1236,\"samsung-galaxy-s25-offerta-amazon\",\"Samsung Galaxy S25: prezzo della promozione Amazon di ottobre 2026\"],[1251,\"sconto-chromebook-mediaworld\",\"Chromebook: come funzionava l'extra sconto MW Club di 50 euro a ottobre 2026\"],[1321,\"netgear-nighthawk-rs200-offerta-wifi-7\",\"NETGEAR Nighthawk RS200: caratteristiche e prezzo della promozione di ottobre 2026\"],[1334,\"hp-envy-6120e-offerta-stampante-multifunzione\",\"HP Envy 6120e: caratteristiche e prezzo della promozione di ottobre 2026\"],[1351,\"asus-rog-maximus-z890-hero-minimo-storico\",\"ASUS ROG Maximus Z890 Hero: caratteristiche e prezzo della promozione di ottobre 2026\"]]")}

def italian_date(value: str) -> str:
    try:
        d = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        months = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
                  "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")
        return f"{d.day} {months[d.month - 1]} {d.year}"
    except (ValueError, TypeError):
        return "la data di pubblicazione"

def seo_title(title: str, date_label: str) -> str:
    try:
        month_year = " ".join(date_label.split()[1:])
    except Exception:
        month_year = "ottobre 2026"
    base = title.split(":", 1)[0].strip()
    suffix = f": prezzo storico {month_year}"
    room = max(10, 60 - len(suffix))
    if len(base) > room:
        base = base[:room].rsplit(" ", 1)[0].rstrip(" :,-")
    return (base + suffix)[:60]

def seo_description(date_label: str) -> str:
    return (f"Prezzo riferito alla promozione del {date_label}. "
            "Verifica disponibilità, prezzo e condizioni attuali presso il venditore.")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "apply"])
    mode = parser.parse_args().mode
    base = os.getenv("WP_BASE_URL", "").rstrip("/").removesuffix("/wp-json")
    username = os.getenv("WP_USERNAME", "")
    password = os.getenv("WP_APP_PASSWORD", "")
    if base != BASE or not username or not password:
        raise SystemExit("Credenziali WordPress mancanti o dominio inatteso.")
    session = requests.Session()
    session.auth = (username, password)
    session.headers["User-Agent"] = "AIVision-Historical-Offer-Title-Repair/1.0"

    def read(post_id: int) -> dict:
        response = session.get(f"{BASE}/wp-json/wp/v2/posts/{post_id}",
                               params={"context": "edit"},
                               timeout=(8, 30))
        response.raise_for_status()
        return response.json()

    if mode == "prepare":
        changes = []
        for post_id, spec in UPDATES.items():
            post = read(post_id)
            title_obj = post.get("title") or {}
            current_title = str(title_obj.get("raw") or title_obj.get("rendered") or "")
            content_obj = post.get("content") or {}
            raw = content_obj.get("raw")
            seo = post.get("aivision_seo")
            if post.get("status") != "publish" or post.get("slug") != spec["slug"]:
                raise RuntimeError(f"Post {post_id}: stato o slug inatteso; nessuna modifica applicata.")
            if not isinstance(raw, str) or NOTICE_MARKER not in raw:
                raise RuntimeError(f"Post {post_id}: nota storica assente; revisione manuale necessaria.")
            if not isinstance(seo, dict):
                raise RuntimeError(f"Post {post_id}: metadati SEO non disponibili.")
            date_label = italian_date(post.get("date"))
            after_seo = dict(seo)
            after_seo["seo_title"] = seo_title(spec["title"], date_label)
            after_seo["seo_description"] = seo_description(date_label)[:155]
            if not str(after_seo.get("focus_keyphrase") or "").strip():
                after_seo["focus_keyphrase"] = FOCUS_KEYPHRASES.get(post_id, spec["title"].split(":", 1)[0].strip())
            if current_title == spec["title"] and all(
                seo.get(key) == value for key, value in after_seo.items()
            ):
                print(f"Post {post_id}: titolo e SEO già aggiornati, salto.")
                continue
            changes.append({
                "id": post_id, "slug": spec["slug"], "modified": post.get("modified"),
                "before_title": current_title, "after_title": spec["title"],
                "before_content": raw, "before_seo": seo,
                "after_seo": after_seo, "date": post.get("date"),
            })
        payload = {"site": BASE, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "mode": "prepare", "planned_updates": len(changes), "changes": changes}
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        BACKUP.write_text(json.dumps({
            "site": BASE, "created_at": payload["created_at"],
            "posts": [{"id": x["id"], "slug": x["slug"], "modified": x["modified"],
                       "title": x["before_title"], "content_raw": x["before_content"],
                       "aivision_seo": x["before_seo"]} for x in changes]
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Titoli da aggiornare:", len(changes))
        print("Backup integrale creato prima di qualsiasi scrittura.")
        return 0

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if plan.get("site") != BASE or not isinstance(plan.get("changes"), list):
        raise RuntimeError("Piano non valido.")
    results = []
    errors = []
    for row in plan["changes"]:
        try:
            live = read(row["id"])
            live_title = str((live.get("title") or {}).get("raw") or (live.get("title") or {}).get("rendered") or "")
            live_content = (live.get("content") or {}).get("raw")
            if (live.get("status") != "publish" or live.get("slug") != row["slug"]
                    or live.get("modified") != row["modified"] or live_title != row["before_title"]
                    or live_content != row["before_content"] or live.get("aivision_seo") != row["before_seo"]):
                raise RuntimeError(f"Post {row['id']} modificato dopo il backup; salto per evitare sovrascritture.")
            response = session.post(
                f"{BASE}/wp-json/wp/v2/posts/{row['id']}", params={"context": "edit"},
                json={"title": row["after_title"], "aivision_seo": row["after_seo"]},
                timeout=(8, 40), allow_redirects=False)
            if not response.ok:
                raise RuntimeError(f"WordPress HTTP {response.status_code}: {response.text[:900]}")
            saved = read(row["id"])
            saved_title = str((saved.get("title") or {}).get("raw") or (saved.get("title") or {}).get("rendered") or "")
            if saved_title != row["after_title"]:
                raise RuntimeError(f"Verifica titolo fallita per post {row['id']}.")
            saved_seo = saved.get("aivision_seo") or {}
            for key, value in row["after_seo"].items():
                if saved_seo.get(key) != value:
                    raise RuntimeError(f"Verifica SEO {key} fallita per post {row['id']}.")
            results.append({"id": row["id"], "slug": row["slug"], "status": "updated_and_verified",
                            "title": saved_title, "date": row["date"]})
            print(f"Post {row['id']}: titolo e SEO aggiornati e verificati.")
        except Exception as exc:
            error = {"id": row["id"], "slug": row["slug"], "status": "error", "error": str(exc)}
            errors.append(error)
            print(f"Post {row['id']}: ERRORE, saltato senza interrompere il lotto: {exc}")
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps({"completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                  "updated": len(results), "errors": errors, "results": results},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print("Completati:", len(results), "errori:", len(errors))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
