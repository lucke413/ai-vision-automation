"""Publish one due guide from the reviewed editor's queue."""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path

import requests

from wp_publisher import WordPressClient, env_bool, get_timezone, publish_one, save_json


GUIDES = Path(__file__).resolve().parent.parent / "config" / "practical-guides"
PLAN = Path("data/practical_guide_plan.json")
REPORT = Path("data/practical_guide_report.json")
SITE = "https://aivision.altervista.org"


def next_guide(entries: list[dict], today: date, client: WordPressClient) -> dict | None:
    for entry in entries:
        if date.fromisoformat(entry["available_from"]) <= today and not client.existing_post(entry["slug"]):
            return entry
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "publish"))
    args = parser.parse_args()
    dry_run = env_bool("WP_DRY_RUN", True)
    base_url = os.getenv("WP_BASE_URL", SITE).rstrip("/").removesuffix("/wp-json")
    username, password = (os.getenv(key, "") for key in ("WP_USERNAME", "WP_APP_PASSWORD"))
    if base_url != SITE or (not dry_run and not (username and password)):
        raise SystemExit("Configurazione WordPress AI Vision mancante o non valida.")
    client = WordPressClient(base_url, username, password, dry_run)
    now = datetime.now(get_timezone())
    entries = json.loads((GUIDES / "queue.json").read_text(encoding="utf-8"))
    with client.session, requests.Session() as public:
        if args.mode == "prepare":
            PLAN.unlink(missing_ok=True)
            guide = next_guide(entries, now.date(), client)
            if guide:
                save_json(PLAN, {"slug": guide["slug"]})
                print(f"Guida pronta: {guide['slug']}")
            else:
                print("Nessuna nuova guida da pubblicare oggi.")
            return

        slug = json.loads(PLAN.read_text(encoding="utf-8"))["slug"]
        guide = next(item for item in entries if item["slug"] == slug)
        if date.fromisoformat(guide["available_from"]) > now.date():
            raise RuntimeError(f"Guida non ancora prevista: {slug}")
        resources = tuple((resource["label"], resource["url"]) for resource in guide["resources"])
        draft = {
            **guide,
            "story_type": "GUIDA",
            "article_id": slug,
            "source_url": resources[0][1],
            "body_markdown": (GUIDES / f"{slug}.md").read_text(encoding="utf-8"),
        }
        result = publish_one(draft, now, client, public, publish_now=True, reader_resources=resources)
        save_json(REPORT, result)
        print(f"{result['status']} · {result['title']} · {result.get('link')}")
        if not dry_run and result["status"] not in {"published", "already_exists"}:
            raise RuntimeError(f"Pubblicazione della guida non confermata: {slug}")


if __name__ == "__main__":
    main()
