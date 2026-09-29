#!/usr/bin/env python3
"""Esclude dai candidati gli articoli già inviati a WordPress negli ultimi giorni.

Legge i report dei run precedenti dagli artifact GitHub. Se la lettura fallisce,
interrompe il workflow prima di generare altri post: meglio uno slot vuoto
che pubblicare la stessa notizia due volte.
"""

from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "ai_candidates.json"
ARTIFACT_NAME = "ai-vision-wp-publish-report"
LOOKBACK_DAYS = 7  # I feed RSS ammettono notizie degli ultimi due giorni.
API_ROOT = "https://api.github.com"


def api_get(url: str, token: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AI-Vision-History-Filter",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def published_ids(repository: str, token: str) -> set[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    used: set[str] = set()
    page = 1
    while True:
        url = (
            f"{API_ROOT}/repos/{repository}/actions/artifacts"
            f"?name={ARTIFACT_NAME}&per_page=100&page={page}"
        )
        listing = json.loads(api_get(url, token))
        artifacts = listing.get("artifacts")
        if not isinstance(artifacts, list):
            raise RuntimeError("Elenco dei report GitHub non valido.")
        for artifact in artifacts:
            created = datetime.fromisoformat(artifact["created_at"].replace("Z", "+00:00"))
            if created < cutoff or artifact.get("expired"):
                continue
            archive = api_get(artifact["archive_download_url"], token)
            with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
                with zipped.open("wp_publish_report.json") as report_file:
                    report = json.load(report_file)
            if report.get("dry_run"):
                continue
            for item in report.get("items", []):
                if item.get("post_id") and item.get("article_id"):
                    used.add(str(item["article_id"]))
        if len(artifacts) < 100:
            break
        page += 1
    return used


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or not repository or "/" not in repository:
        raise RuntimeError("GITHUB_TOKEN o GITHUB_REPOSITORY mancante.")
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    items = data.get("items")
    if not isinstance(items, list):
        raise RuntimeError("Candidati AI non validi.")
    used = published_ids(repository, token)
    retained = [item for item in items if str(item.get("cluster_id") or item.get("article_id") or "") not in used]
    excluded = len(items) - len(retained)
    data["items"] = retained
    data["total_final_candidates"] = len(retained)
    data["history_excluded"] = excluded
    if not retained and data.get("status") in {"ok", "ok_with_warnings"}:
        data["status"] = "empty"
    temporary = INPUT_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(INPUT_FILE)
    print(f"Report precedenti: {len(used)} ID pubblicati o pianificati; esclusi {excluded} candidati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
