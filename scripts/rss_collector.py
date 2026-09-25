import json
import hashlib
import re
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher

import feedparser
import requests


# ============================================================
# CONFIGURAZIONE
# ============================================================

MAX_AGE_HOURS = 48
MAX_ITEMS_PER_FEED = 25
MAX_TOTAL_ITEMS = 200

# Numero massimo di storie uniche da passare successivamente a Gemini
MAX_GEMINI_CLUSTERS = 80

REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": "AI-Vision-RSS-Collector/2.0"
}


# ============================================================
# FONTI RSS
# ============================================================

FEEDS = [

    # --------------------------------------------------------
    # INTERNAZIONALI
    # --------------------------------------------------------

    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "country": "International",
        "type": "Tech"
    },

    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "country": "International",
        "type": "Tech"
    },

    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "country": "International",
        "type": "Tech"
    },

    {
        "name": "BleepingComputer",
        "url": "https://www.bleepingcomputer.com/feed/",
        "country": "International",
        "type": "Security"
    },

    {
        "name": "The Register",
        "url": "https://www.theregister.com/headlines.atom",
        "country": "International",
        "type": "Tech"
    },

    {
        "name": "OpenAI",
        "url": "https://openai.com/news/rss.xml",
        "country": "International",
        "type": "AI"
    },

    {
        "name": "Google AI",
        "url": "https://blog.google/technology/ai/rss/",
        "country": "International",
        "type": "AI"
    },


    # --------------------------------------------------------
    # ITALIANE
    # --------------------------------------------------------

    {
        "name": "Hardware Upgrade",
        "url": "https://www.hwupgrade.it/rss.xml",
        "country": "Italy",
        "type": "Tech"
    },

    {
        "name": "Tom's Hardware Italia",
        "url": "https://www.tomshw.it/feed/",
        "country": "Italy",
        "type": "Tech"
    },

    {
        "name": "DDay",
        "url": "https://www.dday.it/feed",
        "country": "Italy",
        "type": "Tech"
    },

    {
        "name": "Everyeye Tech",
        "url": "https://tech.everyeye.it/feed/feed_news_rss.asp",
        "country": "Italy",
        "type": "Tech"
    },

    {
        "name": "HDblog",
        "url": "https://www.hdblog.it/feed/",
        "country": "Italy",
        "type": "Tech"
    },

    {
        "name": "SmartWorld",
        "url": "https://www.smartworld.it/feed",
        "country": "Italy",
        "type": "Tech"
    },

    {
        "name": "Multiplayer.it",
        "url": "https://psapp.multiplayer.it/feed/",
        "country": "Italy",
        "type": "Gaming"
    }
]


# ============================================================
# UTILITY
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_title(title):
    title = clean_text(title).lower()

    title = re.sub(r"https?://\S+", "", title)

    title = re.sub(r"[^\w\s]", " ", title)

    title = re.sub(r"\s+", " ", title)

    return title.strip()


def title_tokens(title):
    normalized = normalize_title(title)

    stopwords = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "is",
        "are",
        "il",
        "lo",
        "la",
        "i",
        "gli",
        "le",
        "di",
        "del",
        "della",
        "dei",
        "delle",
        "e",
        "o",
        "per",
        "con",
        "un",
        "una"
    }

    return {
        token
        for token in normalized.split()
        if len(token) >= 3 and token not in stopwords
    }


def title_similarity(title_a, title_b):

    norm_a = normalize_title(title_a)
    norm_b = normalize_title(title_b)

    if not norm_a or not norm_b:
        return 0.0

    sequence_score = SequenceMatcher(
        None,
        norm_a,
        norm_b
    ).ratio()

    tokens_a = title_tokens(title_a)
    tokens_b = title_tokens(title_b)

    if not tokens_a or not tokens_b:
        token_score = 0.0
    else:
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)

        token_score = intersection / union if union else 0.0

    return max(sequence_score, token_score)


def make_id(url, title):

    base = f"{url}|{title}"

    return hashlib.sha256(
        base.encode("utf-8")
    ).hexdigest()[:16]


def parse_date(entry):

    parsed = None

    if getattr(entry, "published_parsed", None):
        parsed = entry.published_parsed

    elif getattr(entry, "updated_parsed", None):
        parsed = entry.updated_parsed

    if parsed:
        try:
            return datetime(
                *parsed[:6],
                tzinfo=timezone.utc
            )
        except Exception:
            pass

    return datetime.now(timezone.utc)


def get_image(entry):

    # media_content
    media_content = getattr(entry, "media_content", None)

    if media_content:

        for media in media_content:

            if isinstance(media, dict):

                url = media.get("url")

                if url:
                    return url

    # media_thumbnail
    media_thumbnail = getattr(entry, "media_thumbnail", None)

    if media_thumbnail:

        for media in media_thumbnail:

            if isinstance(media, dict):

                url = media.get("url")

                if url:
                    return url

    # enclosure
    enclosures = getattr(entry, "enclosures", None)

    if enclosures:

        for enclosure in enclosures:

            if isinstance(enclosure, dict):

                url = enclosure.get("href") or enclosure.get("url")

                if url:
                    return url

    return None


# ============================================================
# CONTROLLO FEED
# ============================================================

def check_feed(feed):

    name = feed["name"]
    url = feed["url"]

    result = {
        "name": name,
        "url": url,
        "country": feed["country"],
        "type": feed["type"],
        "status": "ERRORE",
        "http_status": None,
        "articles": 0,
        "message": ""
    }

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        result["http_status"] = response.status_code

        if response.status_code != 200:

            result["message"] = (
                f"HTTP {response.status_code}"
            )

            return result

        content = response.content

        if not content:

            result["status"] = "VUOTO"

            result["message"] = "Risposta vuota"

            return result

        parsed = feedparser.parse(content)

        if getattr(parsed, "bozo", False):

            bozo_exception = getattr(
                parsed,
                "bozo_exception",
                None
            )

            if not parsed.entries:

                result["status"] = "ERRORE"

                result["message"] = (
                    f"Feed non interpretabile: {bozo_exception}"
                )

                return result

        articles = len(parsed.entries)

        result["articles"] = articles

        if articles == 0:

            result["status"] = "VUOTO"

            result["message"] = "Nessun articolo trovato"

            return result

        result["status"] = "OK"

        result["message"] = (
            f"{articles} articoli disponibili"
        )

        return result

    except requests.RequestException as exc:

        result["status"] = "ERRORE"

        result["message"] = (
            f"Errore rete: {exc}"
        )

        return result

    except Exception as exc:

        result["status"] = "ERRORE"

        result["message"] = (
            f"Errore: {exc}"
        )

        return result


# ============================================================
# RACCOLTA FEED
# ============================================================

def collect_feed(feed):

    name = feed["name"]
    url = feed["url"]

    items = []

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            return items

        parsed = feedparser.parse(response.content)

        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(hours=MAX_AGE_HOURS)
        )

        for entry in parsed.entries[:MAX_ITEMS_PER_FEED]:

            title = clean_text(
                getattr(entry, "title", "")
            )

            link = getattr(entry, "link", "")

            if not title or not link:
                continue

            published = parse_date(entry)

            if published < cutoff:
                continue

            description = clean_text(
                getattr(
                    entry,
                    "summary",
                    getattr(entry, "description", "")
                )
            )

            image = get_image(entry)

            item = {
                "id": make_id(link, title),
                "title": title,
                "link": link,
                "description": description,
                "published": published.isoformat(),
                "source": name,
                "country": feed["country"],
                "type": feed["type"],
                "image": image
            }

            items.append(item)

    except Exception as exc:

        print(
            f"   Errore raccolta {name}: {exc}"
        )

    return items


# ============================================================
# DEDUPLICAZIONE ESATTA
# ============================================================

def remove_exact_duplicates(items):

    seen = set()
    unique = []

    for item in items:

        key = (
            item["link"].strip().lower()
            or normalize_title(item["title"])
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(item)

    return unique


# ============================================================
# CLUSTERING
# ============================================================

def build_clusters(items):

    clusters = []

    for item in items:

        best_cluster = None
        best_score = 0.0

        for cluster in clusters:

            representative = cluster["items"][0]

            score = title_similarity(
                item["title"],
                representative["title"]
            )

            if score > best_score:

                best_score = score
                best_cluster = cluster

        # Soglia per considerare due titoli
        # appartenenti alla stessa storia
        if best_cluster and best_score >= 0.62:

            best_cluster["items"].append(item)

        else:

            cluster_id = hashlib.sha256(
                item["id"].encode("utf-8")
            ).hexdigest()[:12]

            clusters.append({
                "cluster_id": cluster_id,
                "items": [item]
            })

    return clusters


# ============================================================
# PREPARAZIONE PER GEMINI
# ============================================================

def prepare_for_ai(clusters):

    prepared = []

    # Prima le storie con più fonti
    clusters = sorted(
        clusters,
        key=lambda cluster: len(cluster["items"]),
        reverse=True
    )

    for cluster in clusters[:MAX_GEMINI_CLUSTERS]:

        items = cluster["items"]

        sources = []

        for item in items:

            sources.append({
                "source": item["source"],
                "country": item["country"],
                "title": item["title"],
                "description": item["description"],
                "url": item["link"],
                "published": item["published"]
            })

        representative = items[0]

        prepared.append({
            "cluster_id": cluster["cluster_id"],
            "title": representative["title"],
            "description": representative["description"],
            "published": representative["published"],
            "source_count": len(sources),
            "sources": sources
        })

    return prepared


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("==============================================")
    print("       AI VISION - RSS COLLECTOR 2.0")
    print("==============================================")
    print()

    print("CONTROLLO AUTOMATICO DEI FEED")
    print("----------------------------------------------")

    feed_status = []

    working_feeds = []

    for feed in FEEDS:

        status = check_feed(feed)

        feed_status.append(status)

        if status["status"] == "OK":

            working_feeds.append(feed)

            print(
                f"OK       {feed['name']:<25} "
                f"{status['articles']} articoli"
            )

        elif status["status"] == "VUOTO":

            print(
                f"VUOTO    {feed['name']:<25} "
                f"{status['message']}"
            )

        else:

            print(
                f"ERRORE   {feed['name']:<25} "
                f"{status['message']}"
            )

    print()
    print(
        f"Feed funzionanti: "
        f"{len(working_feeds)}/{len(FEEDS)}"
    )

    print()
    print("RACCOLTA NOTIZIE")
    print("----------------------------------------------")

    all_items = []

    for feed in working_feeds:

        items = collect_feed(feed)

        print(
            f"{feed['name']:<25} "
            f"{len(items)} articoli validi"
        )

        all_items.extend(items)

    # Limite globale
    all_items = all_items[:MAX_TOTAL_ITEMS]

    print()
    print(
        f"Articoli raccolti: {len(all_items)}"
    )

    # --------------------------------------------------------
    # DEDUP
    # --------------------------------------------------------

    before_dedup = len(all_items)

    unique_items = remove_exact_duplicates(
        all_items
    )

    removed_duplicates = (
        before_dedup - len(unique_items)
    )

    print(
        f"Duplicati esatti eliminati: "
        f"{removed_duplicates}"
    )

    # --------------------------------------------------------
    # CLUSTER
    # --------------------------------------------------------

    clusters = build_clusters(
        unique_items
    )

    print(
        f"Storie/cluster individuati: "
        f"{len(clusters)}"
    )

    # --------------------------------------------------------
    # PREPARAZIONE GEMINI
    # --------------------------------------------------------

    ai_items = prepare_for_ai(
        clusters
    )

    print(
        f"Cluster preparati per Gemini: "
        f"{len(ai_items)}"
    )

    # --------------------------------------------------------
    # RISULTATO
    # --------------------------------------------------------

    output = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "config": {
            "max_age_hours": MAX_AGE_HOURS,
            "max_items_per_feed": MAX_ITEMS_PER_FEED,
            "max_total_items": MAX_TOTAL_ITEMS,
            "max_gemini_clusters": MAX_GEMINI_CLUSTERS
        },

        "feed_status": feed_status,

        "statistics": {
            "feeds_total": len(FEEDS),
            "feeds_working": len(working_feeds),
            "articles_collected": len(all_items),
            "articles_after_dedup": len(unique_items),
            "duplicates_removed": removed_duplicates,
            "clusters_total": len(clusters),
            "clusters_for_gemini": len(ai_items)
        },

        "items": ai_items
    }

    with open(
        "data/rss_items.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("==============================================")
    print("RSS COLLECTOR COMPLETATO")
    print("==============================================")
    print()


if __name__ == "__main__":
    main()
