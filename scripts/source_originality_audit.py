"""Inspect recorded originality controls and compare a current sample with its sources."""
from __future__ import annotations

import collections
import io
import json
import os
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor

from article_generator import enrich_source
from editorial_originality import assess_originality
from history_filter import api_get, list_artifacts
from public_source_links import clean_source_links, marked_source_url


def recorded_checks() -> tuple[dict[int, dict], int]:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not repository or not token:
        return {}, 0
    artifacts = list_artifacts(repository, token, "ai-vision-wp-publish-report")
    artifacts.sort(key=lambda artifact: artifact.get("created_at", ""), reverse=True)

    def read(artifact):
        try:
            with zipfile.ZipFile(io.BytesIO(api_get(artifact["archive_download_url"], token))) as zipped:
                with zipped.open("wp_publish_report.json") as source:
                    report = json.load(source)
            return [] if report.get("dry_run") else report.get("items", [])
        except (OSError, KeyError, ValueError, zipfile.BadZipFile):
            return None

    records = {}
    unreadable = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for items in pool.map(read, artifacts):
            if items is None:
                unreadable += 1
                continue
            for item in items:
                if isinstance(item, dict) and item.get("post_id") and item.get("status") == "scheduled":
                    records.setdefault(int(item["post_id"]), item)
    return records, unreadable


def audit_originality(posts: list[dict], records: dict[int, dict]) -> tuple[dict, list[dict]]:
    by_status = {state: collections.Counter() for state in ("publish", "future")}
    sample = []
    for post in posts:
        record = records.get(post["id"], {})
        check = record.get("originality_check") or {}
        status = check.get("status", "not_recorded")
        by_status[post["status"]][status] += 1
        content = post["content"]["raw"]
        source = str(record.get("source_url") or marked_source_url(content))
        if source and status != "not_applicable":
            sample.append((post, source, record))
    # Compare the most recent published articles and every scheduled article
    # with traceable sources. Use stored check results for the rest of the site.
    latest = sorted((entry for entry in sample if entry[0]["status"] == "publish"),
                    key=lambda entry: entry[0].get("date") or "", reverse=True)[:15]
    latest += [entry for entry in sample if entry[0]["status"] == "future"]

    def verify(entry):
        post, source, record = entry
        article, _ = clean_source_links(post["content"]["raw"], source)
        # Omit figures, affiliate disclosures and appended related links
        # contributed by WordPress, rather than by the article writer.
        article = re.sub(r"<figure\b[^>]*>.*?</figure\s*>|<div\b[^>]*\bav-amazon-affiliate\b[^>]*>.*?</div\s*>",
                         "", article, flags=re.I | re.S)
        article = re.sub(r"</(?:p|h[1-3]|li)\s*>", "\n\n", article, flags=re.I)
        current_source = enrich_source({"url": source, "ai_cyber_topic": record.get("ai_cyber_topic")})
        check = assess_originality(
            article, current_source.get("source_text") or "",
            source_status=current_source.get("source_text_status"),
        )
        status = check["status"]
        if check["source_words"] < 100:
            status = "source_unavailable"
        return {
            "id": post["id"], "status_wp": post["status"], "check": status,
            "source_words": check["source_words"],
            "longest_exact_match_words": check["longest_exact_match_words"],
            "shared_7gram_ratio": check["shared_7gram_ratio"],
            "structural_similarity": check.get("structural_similarity", 0),
        }

    with ThreadPoolExecutor(max_workers=6) as pool:
        return by_status, list(pool.map(verify, latest))
