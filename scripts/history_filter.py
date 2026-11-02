#!/usr/bin/env python3
"""Deduplica i candidati e recupera riserve recenti dai run precedenti.

Le riserve sono candidate già valutate dall'AI, conservate negli artifact
giornalieri GitHub. Il recupero è best-effort: un problema nella lettura delle
riserve non deve bloccare la raccolta o la pubblicazione del lotto corrente.
Il controllo delle notizie già pubblicate resta invece obbligatorio quando
sono presenti candidati.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import zipfile

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "ai_candidates.json"
PUBLISHED_ARTIFACT_NAME = "ai-vision-wp-publish-report"
RESERVE_ARTIFACT_NAME = "ai-vision-daily-articles"
LOOKBACK_DAYS = 7
RESERVE_MAX_AGE_HOURS = 48
MAX_HISTORICAL_RESERVES = 24
API_ROOT = "https://api.github.com"


class ArtifactRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Non inoltra il token GitHub al server dell'archivio firmato."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and urlsplit(req.full_url).netloc != urlsplit(newurl).netloc:
            for name in ("Authorization", "Accept", "X-github-api-version"):
                redirected.remove_header(name)
        return redirected


def api_get(url: str, token: str) -> bytes:
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AI-Vision-History-Filter",
    })
    with urllib.request.build_opener(ArtifactRedirectHandler()).open(request, timeout=30) as response:
        return response.read()


def parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def canonical_url(value: object) -> str:
    try:
        parts = urlsplit(str(value or "").strip())
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return ""
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), ""))
    except ValueError:
        return ""


def candidate_id(item: dict) -> str:
    value = str(item.get("cluster_id") or item.get("article_id") or "").strip()
    if value:
        return value
    url = canonical_url(item.get("url"))
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20] if url else ""


def list_artifacts(repository: str, token: str, name: str) -> list[dict]:
    found: list[dict] = []
    page = 1
    while True:
        url = f"{API_ROOT}/repos/{repository}/actions/artifacts?name={name}&per_page=100&page={page}"
        listing = json.loads(api_get(url, token))
        artifacts = listing.get("artifacts")
        if not isinstance(artifacts, list):
            raise RuntimeError("Elenco degli artifact GitHub non valido.")
        found.extend(a for a in artifacts if isinstance(a, dict) and not a.get("expired"))
        if len(artifacts) < 100:
            break
        page += 1
    return found


def published_ids(repository: str, token: str) -> set[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    used: set[str] = set()
    for artifact in list_artifacts(repository, token, PUBLISHED_ARTIFACT_NAME):
        created = parse_datetime(artifact.get("created_at"))
        if created is None or created < cutoff:
            continue
        archive = api_get(artifact["archive_download_url"], token)
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            with zipped.open("wp_publish_report.json") as report_file:
                report = json.load(report_file)
        if report.get("dry_run"):
            continue
        for item in report.get("items", []):
            if isinstance(item, dict) and item.get("post_id") and item.get("article_id"):
                used.add(str(item["article_id"]))
    return used


def historical_reserves(repository: str, token: str, now: datetime | None = None) -> list[dict]:
    """Legge le riserve recenti; ignora artifact malformati senza bloccare il run."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=RESERVE_MAX_AGE_HOURS)
    candidates: list[tuple[datetime, dict]] = []
    try:
        artifacts = list_artifacts(repository, token, RESERVE_ARTIFACT_NAME)
    except Exception as exc:
        print(f"AVVISO riserve: elenco artifact non disponibile ({type(exc).__name__}); uso i candidati correnti.")
        return []
    for artifact in artifacts:
        created = parse_datetime(artifact.get("created_at"))
        if created is None or created < cutoff or not artifact.get("archive_download_url"):
            continue
        try:
            archive = api_get(artifact["archive_download_url"], token)
            with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
                with zipped.open("daily_articles.json") as source:
                    previous = json.load(source)
            reserves = previous.get("reserve_items", [])
            if not isinstance(reserves, list):
                continue
            for raw in reserves:
                if not isinstance(raw, dict) or not raw.get("title"):
                    continue
                url = canonical_url(raw.get("url"))
                if not url:
                    continue
                published = parse_datetime(raw.get("published"))
                freshness = published or created
                if freshness < cutoff or freshness > now + timedelta(hours=1):
                    continue
                item = dict(raw)
                item["url"] = url
                item["article_id"] = candidate_id(item)
                item["reserve_origin_run"] = artifact.get("workflow_run", {}).get("id")
                candidates.append((freshness, item))
        except Exception as exc:
            print(f"AVVISO riserve: artifact {artifact.get('id', '?')} non leggibile ({type(exc).__name__}); continuo.")
    # Più recenti prima; URL e ID eliminano duplicati tra run diversi.
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    result: list[dict] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for _, item in candidates:
        identifier = candidate_id(item)
        url = canonical_url(item.get("url"))
        if not identifier or identifier in seen_ids or url in seen_urls:
            continue
        seen_ids.add(identifier)
        seen_urls.add(url)
        result.append(item)
        if len(result) >= MAX_HISTORICAL_RESERVES:
            break
    return result


def main() -> int:
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    items = data.get("items")
    if not isinstance(items, list):
        raise RuntimeError("Candidati AI non validi.")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or not repository or "/" not in repository:
        if items:
            raise RuntimeError("GITHUB_TOKEN o GITHUB_REPOSITORY mancante.")
        print("Nessun candidato AI e nessun token storico: continuo con lotto vuoto.")
        return 0

    reserves = historical_reserves(repository, token)
    current_ids = {candidate_id(x) for x in items if isinstance(x, dict)}
    current_urls = {canonical_url(x.get("url")) for x in items if isinstance(x, dict)}
    added = []
    for item in reserves:
        if candidate_id(item) in current_ids or canonical_url(item.get("url")) in current_urls:
            continue
        added.append(item)
        current_ids.add(candidate_id(item))
        current_urls.add(canonical_url(item.get("url")))

    if added:
        data["items"].extend(added)
        data["total_received"] = int(data.get("total_received", len(items))) + len(added)
        data["total_final_candidates"] = len(data["items"])
        if data.get("status") == "empty":
            data["status"] = "ok_with_warnings"
        print(f"Riserve persistenti recuperate: {len(added)} candidate recenti.")

    # Con un lotto vuoto il controllo storico non è necessario, ma il recupero
    # delle riserve è stato comunque tentato.
    if not data["items"]:
        data["status"] = "empty"
        print("Nessun candidato corrente o di riserva disponibile.")
    else:
        used = published_ids(repository, token)
        before = len(data["items"])
        retained = [item for item in data["items"]
                    if str(item.get("cluster_id") or item.get("article_id") or "") not in used]
        data["items"] = retained
        data["total_final_candidates"] = len(retained)
        data["history_excluded"] = int(data.get("history_excluded", 0)) + before - len(retained)
        if not retained:
            data["status"] = "empty"
        print(f"Report precedenti: {len(used)} ID pubblicati o pianificati; esclusi {before - len(retained)} candidati.")

    temporary = INPUT_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(INPUT_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
