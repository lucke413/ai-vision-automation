#!/usr/bin/env python3
"""Raccoglie fonti per l'approfondimento quotidiano su IA e cybersicurezza."""
from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

if __package__:
    from .rss_collector import BASE_DIR, canonical_url, clean_html, extract_entry_url, fetch_feed, parse_date
else:
    from rss_collector import BASE_DIR, canonical_url, clean_html, extract_entry_url, fetch_feed, parse_date


OUTPUT_FILE = BASE_DIR / "data" / "ai_cyber_candidates.json"
TAG = "IA e cybersicurezza"
FEEDS = {
    "Microsoft Security": ("https://www.microsoft.com/en-us/security/blog/feed/", "www.microsoft.com"),
    "Google Threat Intelligence": ("https://cloudblog.withgoogle.com/topics/threat-intelligence/rss/", "cloud.google.com"),
    "NCSC": ("https://www.ncsc.gov.uk/api/1/services/v1/report-rss-feed.xml", "www.ncsc.gov.uk"),
    "OpenAI": ("https://openai.com/news/rss.xml", "openai.com"),
    "BleepingComputer": ("https://www.bleepingcomputer.com/feed/", "www.bleepingcomputer.com"),
}
AI = re.compile(r"\b(?:ai|artificial intelligence|generative ai|llms?|llmjacking|machine learning|agentic|coding agents?|copilot|chatgpt|deepfakes?|prompt injection)\b", re.I)
SECURITY = re.compile(r"\b(?:cyber\w*|secur\w*|threat\w*|attack\w*|hijack\w*|vulnerab\w*|phishing|fraud|malware|breach\w*|authenticat\w*|permissions?|prompt injection|poison\w*|data leak\w*|sleeper agents?|supply chain)\b", re.I)
TOPICS = {
    "identita-e-permessi": (r"authenticat\w*|permissions?|privileges?|credentials?|identity|oauth", "identità e permessi degli agenti"),
    "impersonificazione": (r"deepfakes?|phishing|impersonat\w*|fraud|scams?|voice clon\w*", "phishing e impersonificazione"),
    "catena-di-fornitura": (r"supply chain|dependencies|model weights|post.training|model poisoning", "catena di fornitura dei modelli"),
    "istruzioni-e-input": (r"prompt injection|untrusted (?:input|content)|tool misuse", "istruzioni e contenuti non affidabili"),
    "protezione-dei-dati": (r"privacy|data leakage|data leaks?|data exposure|sensitive information|secrets?", "protezione dei dati"),
    "rilevamento-e-risposta": (r"detect\w*|incident response|monitor\w*|triage|sleeper agents?", "rilevamento e risposta agli incidenti"),
    "sicurezza-dei-sistemi": (r"secure deployment|vulnerab\w*|harden\w*|secure by design", "sicurezza dei sistemi di IA"),
    "analisi-delle-minacce": (r"cyber\w*|secur\w*|threat\w*|attack\w*", "analisi delle minacce legate all'IA"),
}
REFERENCE_TOPICS = (
    ("istruzioni-e-input", "Riconoscere e contenere la prompt injection negli assistenti IA",
     "https://genai.owasp.org/llmrisk/llm01-prompt-injection/"),
    ("protezione-dei-dati", "Come ridurre il rischio di divulgazione di dati sensibili nelle app IA",
     "https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/"),
    ("catena-di-fornitura", "Come valutare la provenienza dei modelli e delle dipendenze IA",
     "https://genai.owasp.org/llmrisk/llm032025-supply-chain/"),
    ("identita-e-permessi", "Agenti IA con accesso a strumenti esterni: come limitare i permessi",
     "https://genai.owasp.org/llmrisk/llm062025-excessive-agency/"),
    ("sicurezza-dei-sistemi", "Sviluppare sistemi di intelligenza artificiale sicuri dalla progettazione",
     "https://www.ncsc.gov.uk/collection/guidelines-secure-ai-system-development/guidelines"),
    ("rilevamento-e-risposta", "Monitoraggio e risposta agli incidenti nei sistemi di intelligenza artificiale",
     "https://www.ncsc.gov.uk/collection/guidelines-secure-ai-system-development/guidelines/secure-operation-maintenance"),
)
SOURCE_HOSTS = frozenset({host for _, host in FEEDS.values()} | {
    "blog.google", "cloudblog.withgoogle.com", "cloud.google.com", "genai.owasp.org",
    "www.ncsc.gov.uk", "www.microsoft.com", "bleepingcomputer.com",
})
TOPIC_KEY = "ai_cyber_topic"
CYBER_TITLE = re.compile(
    r"\b(?:cyber\w*|sicurezza informatica|ransomware|malware|phishing|infostealer|"
    r"attacc[oi] informatic[oi]|vulnerabilit[àa]|cve-\d{4}-\d+|data breach|prompt injection|"
    r"violazion[ei] dei dati|furto di credenziali|truff\w*\s+(?:online|digital\w*|con deepfake))\b",
    re.I,
)
EDITORIAL_BRIEF = (
    "Approfondimento di IA e cybersicurezza per lettori non specialisti. "
    "Apri con un caso concreto e spiega perché conta. Illustra un meccanismo tecnico, "
    "definendo i termini alla prima occorrenza, con un esempio ipotetico innocuo "
    "oppure un confronto utile. Spiega almeno un limite e indica misure difensive "
    "verificabili. Ometti payload, istruzioni di sfruttamento e catene d'attacco riproducibili. "
    "Per i documenti di riferimento scrivi un pezzo di contesto e mantieni le date reali della fonte."
)


def is_cybersecurity(item: dict) -> bool:
    title = html.unescape(str(item.get("title") or ""))
    return bool(item.get(TOPIC_KEY) or item.get("category") == "Sicurezza"
                or item.get("story_type") == "SICUREZZA" or CYBER_TITLE.search(title))


def topic_for(text: str) -> str:
    if not AI.search(text) or not SECURITY.search(text):
        return ""
    return next((key for key, (pattern, _) in TOPICS.items() if re.search(r"\b(?:" + pattern + r")\b", text, re.I)), "")


def source_identity(url: str) -> str:
    parts = urlsplit(canonical_url(url))
    if not parts.hostname:
        return ""
    return parts.hostname.removeprefix("www.") + parts.path.rstrip("/")


def load_feed(source: tuple[str, tuple[str, str]], now: datetime) -> list[dict]:
    name, (feed_url, _) = source
    parsed, _ = fetch_feed(name, {"url": feed_url})
    if parsed is None:
        return []
    candidates = []
    for entry in parsed.entries[:40]:
        date = parse_date(entry)
        if not date or not now - timedelta(days=21) <= date <= now + timedelta(hours=1):
            continue
        title = clean_html(entry.get("title"))
        description = clean_html(entry.get("summary") or entry.get("description"))
        url = canonical_url(extract_entry_url(entry))
        parsed_url = urlsplit(url)
        if not title or parsed_url.scheme != "https" or parsed_url.netloc not in SOURCE_HOSTS:
            continue
        # Il titolo deve portare entrambi i temi: un cenno nel testo può essere incidentale.
        topic = topic_for(title)
        if not topic:
            continue
        text = " ".join(clean_html(part.get("value")) for part in entry.get("content", []))
        candidates.append({
            "title": title, "url": url, "source": name,
            "description": description[:3500], "published": date.isoformat(),
            "feed_text": text[:18000], TOPIC_KEY: topic,
            "category": "Sicurezza", "story_type": "ANALISI",
        })
    return candidates


def collect_candidates(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=len(FEEDS)) as pool:
        feeds = list(pool.map(lambda source: load_feed(source, now), FEEDS.items()))
    ranked = sorted((item for feed in feeds for item in feed),
                    key=lambda item: item["published"], reverse=True)
    ranked.extend({
        "title": title, "url": url, "source": "OWASP GenAI Security Project" if "owasp" in url else "NCSC",
        "description": "Approfondimento di contesto basato sulle raccomandazioni ufficiali.",
        "category": "Sicurezza", "story_type": "ANALISI",
        TOPIC_KEY: topic, "ai_cyber_reference": True,
    } for topic, title, url in REFERENCE_TOPICS)
    unique = {}
    for item in ranked:
        unique.setdefault(source_identity(item["url"]), item)
    return list(unique.values())


def main() -> int:
    items = collect_candidates()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(OUTPUT_FILE)
    print(f"IA e cybersicurezza: {len(items)} fonti candidate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
