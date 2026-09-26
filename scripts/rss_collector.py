import json
import hashlib
import re
import os
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
MAX_GEMINI_CLUSTERS = 80

REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": "AI-Vision-RSS-Collector/2.1"
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
# STOPWORDS
# ============================================================

STOPWORDS = {
    # Inglese
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
    "this",
    "that",
    "from",
    "into",
    "after",
    "before",
    "new",
    "news",
    "how",
    "why",
    "what",
    "its",
    "it",
    "as",
    "by",
    "over",
    "more",

    # Italiano
    "il",
    "lo",
    "la",
    "i",
    "gli",
    "le",
    "di",
    "del",
    "della",
    "delle",
    "dei",
    "degli",
    "e",
    "o",
    "per",
    "con",
    "un",
    "una",
    "uno",
    "da",
    "dal",
    "dalla",
    "su",
    "nel",
    "nella",
    "nelle",
    "nei",
    "degli",
    "come",
    "che",
    "non",
    "anche",
    "tra",
    "fra",
    "più",
    "nuovo",
    "nuova",
    "nuovi",
    "nuove",
    "oggi",
    "ora",
    "sul",
    "sulla",
    "questo",
    "questa",
    "questi",
    "queste"
}


# ============================================================
# UTILITY TESTO
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_text(text):
    text = clean_text(text).lower()

    text = re.sub(
        r"https?://\S+",
        " ",
        text
    )

    text = text.replace("&amp;", " and ")

    text = re.sub(
        r"[^\w\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def normalize_title(title):
    return normalize_text(title)


def extract_keywords(text, max_keywords=30):

    normalized = normalize_text(text)

    words = normalized.split()

    keywords = []

    for word in words:

        if len(word) < 4:
            continue

        if word in STOPWORDS:
            continue

        if word.isdigit():
            continue

        if word not in keywords:
            keywords.append(word)

    return keywords[:max_keywords]


def keyword_set(text):

    return set(
        extract_keywords(text)
    )


# ============================================================
# SIMILARITÀ
# ============================================================

def sequence_similarity(text_a, text_b):

    if not text_a or not text_b:
        return 0.0

    return SequenceMatcher(
        None,
        text_a,
        text_b
    ).ratio()


def keyword_similarity(text_a, text_b):

    words_a = keyword_set(text_a)
    words_b = keyword_set(text_b)

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    union = words_a | words_b

    return (
        len(intersection) / len(union)
        if union
        else 0.0
    )


def calculate_story_similarity(
    item_a,
    item_b
):

    title_a = normalize_title(
        item_a.get("title", "")
    )

    title_b = normalize_title(
        item_b.get("title", "")
    )

    description_a = normalize_text(
        item_a.get("description", "")
    )

    description_b = normalize_text(
        item_b.get("description", "")
    )

    # --------------------------------------------------------
    # Similarità titoli
    # --------------------------------------------------------

    title_sequence = sequence_similarity(
        title_a,
        title_b
    )

    title_keywords = keyword_similarity(
        title_a,
        title_b
    )

    title_score = max(
        title_sequence,
        title_keywords
    )

    # --------------------------------------------------------
    # Similarità descrizioni
    # --------------------------------------------------------

    description_keywords = keyword_similarity(
        description_a,
        description_b
    )

    # --------------------------------------------------------
    # Keyword combinate titolo + descrizione
    # --------------------------------------------------------

    combined_a = (
        title_a
        + " "
        + description_a
    )

    combined_b = (
        title_b
        + " "
        + description_b
    )

    combined_keywords = keyword_similarity(
        combined_a,
        combined_b
    )

    # --------------------------------------------------------
    # Score finale
    # --------------------------------------------------------

    score = (
        title_score * 0.60
        + description_keywords * 0.15
        + combined_keywords * 0.25
    )

    return score


# ============================================================
# ID
# ============================================================

def make_id(url, title):

    base = f"{url}|{title}"

    return hashlib.sha256(
        base.encode("utf-8")
    ).hexdigest()[:16]


# ============================================================
# DATA
# ============================================================

def parse_date(entry):

    parsed = None

    if getattr(
        entry,
        "published_parsed",
        None
    ):
        parsed = entry.published_parsed

    elif getattr(
        entry,
        "updated_parsed",
        None
    ):
        parsed = entry.updated_parsed

    if parsed:

        try:

            return datetime(
                *parsed[:6],
                tzinfo=timezone.utc
            )

        except Exception:
            pass

    return datetime.now(
        timezone.utc
    )


# ============================================================
# IMMAGINE
# ============================================================

def get_image(entry):

    media_content = getattr(
        entry,
        "media_content",
        None
    )

    if media_content:

        for media in media_content:

            if isinstance(
                media,
                dict
            ):

                url = media.get(
                    "url"
                )

                if url:
                    return url

    media_thumbnail = getattr(
        entry,
        "media_thumbnail",
        None
    )

    if media_thumbnail:

        for media in media_thumbnail:

            if isinstance(
                media,
                dict
            ):

                url = media.get(
                    "url"
                )

                if url:
                    return url

    enclosures = getattr(
        entry,
        "enclosures",
        None
    )

    if enclosures:

        for enclosure in enclosures:

            if isinstance(
                enclosure,
                dict
            ):

                url = (
                    enclosure.get(
                        "href"
                    )
                    or enclosure.get(
                        "url"
                    )
                )

                if url:
                    return url

    return None


# ============================================================
# CONTROLLO AUTOMATICO FEED
# ============================================================

def check_feed(feed):

    name = feed["name"]
    url = feed["url"]

    result = {

        "name": name,

        "url": url,

        "country":
            feed["country"],

        "type":
            feed["type"],

        "status":
            "ERRORE",

        "http_status":
            None,

        "articles":
            0,

        "message":
            ""
    }

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        result[
            "http_status"
        ] = response.status_code

        if response.status_code != 200:

            result[
                "message"
            ] = (
                f"HTTP "
                f"{response.status_code}"
            )

            return result

        content = response.content

        if not content:

            result[
                "status"
            ] = "VUOTO"

            result[
                "message"
            ] = "Risposta vuota"

            return result

        parsed = feedparser.parse(
            content
        )

        if getattr(
            parsed,
            "bozo",
            False
        ):

            bozo_exception = getattr(
                parsed,
                "bozo_exception",
                None
            )

            if not parsed.entries:

                result[
                    "status"
                ] = "ERRORE"

                result[
                    "message"
                ] = (
                    "Feed non interpretabile: "
                    f"{bozo_exception}"
                )

                return result

        articles = len(
            parsed.entries
        )

        result[
            "articles"
        ] = articles

        if articles == 0:

            result[
                "status"
            ] = "VUOTO"

            result[
                "message"
            ] = (
                "Nessun articolo trovato"
            )

            return result

        result[
            "status"
        ] = "OK"

        result[
            "message"
        ] = (
            f"{articles} articoli disponibili"
        )

        return result

    except requests.RequestException as exc:

        result[
            "status"
        ] = "ERRORE"

        result[
            "message"
        ] = (
            f"Errore rete: {exc}"
        )

        return result

    except Exception as exc:

        result[
            "status"
        ] = "ERRORE"

        result[
            "message"
        ] = (
            f"Errore: {exc}"
        )

        return result


# ============================================================
# RACCOLTA
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

        parsed = feedparser.parse(
            response.content
        )

        cutoff = (
            datetime.now(
                timezone.utc
            )
            - timedelta(
                hours=MAX_AGE_HOURS
            )
        )

        for entry in parsed.entries[
            :MAX_ITEMS_PER_FEED
        ]:

            title = clean_text(
                getattr(
                    entry,
                    "title",
                    ""
                )
            )

            link = getattr(
                entry,
                "link",
                ""
            )

            if not title or not link:
                continue

            published = parse_date(
                entry
            )

            if published < cutoff:
                continue

            description = clean_text(
                getattr(
                    entry,
                    "summary",
                    getattr(
                        entry,
                        "description",
                        ""
                    )
                )
            )

            image = get_image(
                entry
            )

            item = {

                "id":
                    make_id(
                        link,
                        title
                    ),

                "title":
                    title,

                "link":
                    link,

                "description":
                    description,

                "published":
                    published.isoformat(),

                "source":
                    name,

                "country":
                    feed["country"],

                "type":
                    feed["type"],

                "image":
                    image,

                "keywords":
                    extract_keywords(
                        title
                        + " "
                        + description
                    )
            }

            items.append(
                item
            )

    except Exception as exc:

        print(
            f"   Errore raccolta "
            f"{name}: {exc}"
        )

    return items


# ============================================================
# DEDUPLICAZIONE ESATTA
# ============================================================

def remove_exact_duplicates(
    items
):

    seen_urls = set()
    seen_titles = set()

    unique = []

    for item in items:

        url = (
            item["link"]
            .strip()
            .lower()
        )

        title = normalize_title(
            item["title"]
        )

        # URL identico
        if url in seen_urls:
            continue

        # Titolo identico
        if title in seen_titles:
            continue

        seen_urls.add(url)
        seen_titles.add(title)

        unique.append(
            item
        )

    return unique


# ============================================================
# CLUSTERING 2.1
# ============================================================

def build_clusters(items):

    clusters = []

    for item in items:

        best_cluster = None
        best_score = 0.0

        for cluster in clusters:

            # Confrontiamo la nuova notizia
            # con tutti gli articoli del cluster,
            # non solamente con il primo.
            cluster_best_score = 0.0

            for existing_item in cluster[
                "items"
            ]:

                score = calculate_story_similarity(
                    item,
                    existing_item
                )

                if score > cluster_best_score:
                    cluster_best_score = score

            if cluster_best_score > best_score:

                best_score = (
                    cluster_best_score
                )

                best_cluster = cluster

        # ----------------------------------------------------
        # SOGLIA
        # ----------------------------------------------------

        if (
            best_cluster
            and best_score >= 0.48
        ):

            best_cluster[
                "items"
            ].append(
                item
            )

            best_cluster[
                "similarity_scores"
            ].append(
                round(
                    best_score,
                    3
                )
            )

        else:

            cluster_id = hashlib.sha256(
                item["id"].encode(
                    "utf-8"
                )
            ).hexdigest()[:12]

            clusters.append({

                "cluster_id":
                    cluster_id,

                "items":
                    [item],

                "similarity_scores":
                    []
            })

    return clusters


# ============================================================
# PREPARAZIONE GEMINI
# ============================================================

def prepare_for_ai(
    clusters
):

    prepared = []

    # Prima i cluster con più fonti.
    # Sono potenzialmente più importanti
    # perché più siti stanno trattando
    # la stessa storia.
    clusters = sorted(
        clusters,
        key=lambda cluster: (
            len(
                cluster["items"]
            ),
            max(
                cluster[
                    "similarity_scores"
                ]
                or [0]
            )
        ),
        reverse=True
    )

    for cluster in clusters[
        :MAX_GEMINI_CLUSTERS
    ]:

        items = cluster[
            "items"
        ]

        sources = []

        all_keywords = set()

        for item in items:

            sources.append({

                "source":
                    item["source"],

                "country":
                    item["country"],

                "title":
                    item["title"],

                "description":
                    item["description"],

                "url":
                    item["link"],

                "published":
                    item["published"]
            })

            all_keywords.update(
                item.get(
                    "keywords",
                    []
                )
            )

        # Ordina le fonti per data
        sources.sort(
            key=lambda source:
                source["published"],
            reverse=True
        )

        representative = items[0]

        prepared.append({

            "cluster_id":
                cluster[
                    "cluster_id"
                ],

            "title":
                representative[
                    "title"
                ],

            "description":
                representative[
                    "description"
                ],

            "published":
                representative[
                    "published"
                ],

            "source_count":
                len(sources),

            "sources":
                sources,

            "keywords":
                sorted(
                    all_keywords
                )
        })

    return prepared


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=============================================="
    )
    print(
        "       AI VISION - RSS COLLECTOR 2.1"
    )
    print(
        "=============================================="
    )
    print()

    # --------------------------------------------------------
    # CONTROLLO FEED
    # --------------------------------------------------------

    print(
        "CONTROLLO AUTOMATICO DEI FEED"
    )

    print(
        "----------------------------------------------"
    )

    feed_status = []
    working_feeds = []

    for feed in FEEDS:

        status = check_feed(
            feed
        )

        feed_status.append(
            status
        )

        if status[
            "status"
        ] == "OK":

            working_feeds.append(
                feed
            )

            print(
                f"OK       "
                f"{feed['name']:<25} "
                f"{status['articles']} articoli"
            )

        elif status[
            "status"
        ] == "VUOTO":

            print(
                f"VUOTO    "
                f"{feed['name']:<25} "
                f"{status['message']}"
            )

        else:

            print(
                f"ERRORE   "
                f"{feed['name']:<25} "
                f"{status['message']}"
            )

    print()

    print(
        f"Feed funzionanti: "
        f"{len(working_feeds)}"
        f"/{len(FEEDS)}"
    )

    # --------------------------------------------------------
    # RACCOLTA
    # --------------------------------------------------------

    print()

    print(
        "RACCOLTA NOTIZIE"
    )

    print(
        "----------------------------------------------"
    )

    all_items = []

    for feed in working_feeds:

        items = collect_feed(
            feed
        )

        print(
            f"{feed['name']:<25} "
            f"{len(items)} articoli validi"
        )

        all_items.extend(
            items
        )

    all_items = all_items[
        :MAX_TOTAL_ITEMS
    ]

    print()

    print(
        f"Articoli raccolti: "
        f"{len(all_items)}"
    )

    # --------------------------------------------------------
    # DEDUPLICAZIONE
    # --------------------------------------------------------

    before_dedup = len(
        all_items
    )

    unique_items = (
        remove_exact_duplicates(
            all_items
        )
    )

    removed_duplicates = (
        before_dedup
        - len(unique_items)
    )

    print(
        f"Duplicati esatti eliminati: "
        f"{removed_duplicates}"
    )

    # --------------------------------------------------------
    # CLUSTERING
    # --------------------------------------------------------

    clusters = build_clusters(
        unique_items
    )

    multi_source_clusters = sum(
        1
        for cluster in clusters
        if len(
            cluster["items"]
        ) > 1
    )

    largest_cluster = max(
        (
            len(
                cluster["items"]
            )
            for cluster in clusters
        ),
        default=0
    )

    print(
        f"Storie/cluster individuati: "
        f"{len(clusters)}"
    )

    print(
        f"Cluster con più fonti: "
        f"{multi_source_clusters}"
    )

    print(
        f"Dimensione massima cluster: "
        f"{largest_cluster}"
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
    # CARTELLA DATA
    # --------------------------------------------------------

    os.makedirs(
        "data",
        exist_ok=True
    )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    output = {

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "collector_version":
            "2.1",

        "config": {

            "max_age_hours":
                MAX_AGE_HOURS,

            "max_items_per_feed":
                MAX_ITEMS_PER_FEED,

            "max_total_items":
                MAX_TOTAL_ITEMS,

            "max_gemini_clusters":
                MAX_GEMINI_CLUSTERS,

            "cluster_threshold":
                0.48
        },

        "feed_status":
            feed_status,

        "statistics": {

            "feeds_total":
                len(FEEDS),

            "feeds_working":
                len(working_feeds),

            "articles_collected":
                len(all_items),

            "articles_after_dedup":
                len(unique_items),

            "duplicates_removed":
                removed_duplicates,

            "clusters_total":
                len(clusters),

            "multi_source_clusters":
                multi_source_clusters,

            "largest_cluster":
                largest_cluster,

            "clusters_for_gemini":
                len(ai_items)
        },

        "items":
            ai_items
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

    print(
        "=============================================="
    )

    print(
        "RSS COLLECTOR 2.1 COMPLETATO"
    )

    print(
        "=============================================="
    )

    print()


if __name__ == "__main__":
    main()
