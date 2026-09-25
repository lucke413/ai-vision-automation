#!/usr/bin/env python3

"""
AI Vision - RSS Collector 2.0

Funzioni:
- raccoglie articoli da fonti italiane e internazionali
- filtra gli articoli troppo vecchi
- normalizza titoli e URL
- elimina duplicati esatti
- raggruppa notizie simili
- conserva le diverse fonti della stessa storia
- prepara i cluster per il passaggio a Gemini

NON pubblica nulla.
NON utilizza Gemini.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

import feedparser


# ============================================================
# CONFIGURAZIONE
# ============================================================

MAX_AGE_HOURS = 48
MAX_ITEMS_PER_FEED = 30
MAX_TOTAL_RAW_ITEMS = 300

TITLE_SIMILARITY_THRESHOLD = 0.72

MAX_GEMINI_CLUSTERS = 80

OUTPUT_FILE = Path("data/rss_items.json")


# ============================================================
# FONTI RSS
# ============================================================

FEEDS = [

    # ========================================================
    # 🇮🇹 FONTI ITALIANE
    # ========================================================

    {
        "name": "Hardware Upgrade",
        "url": "http://feeds.hwupgrade.it/rss_news.xml",
        "country": "IT",
        "priority": 8,
        "areas": [
            "Tecnologia",
            "AI",
            "Sicurezza",
            "Hardware",
            "Smartphone",
        ],
    },

    {
        "name": "Tom's Hardware Italia",
        "url": "https://www.tomshw.it/feed-rss",
        "country": "IT",
        "priority": 8,
        "areas": [
            "Tecnologia",
            "AI",
            "Hardware",
            "Smartphone",
            "Guide",
            "Offerte",
        ],
    },

    {
        "name": "DDay.it",
        "url": "https://www.dday.it/feed",
        "country": "IT",
        "priority": 8,
        "areas": [
            "Tecnologia",
            "Smartphone",
            "Hardware",
            "AI",
            "TV",
            "Offerte",
        ],
    },

    {
        "name": "Everyeye Tech",
        "url": "https://tech.everyeye.it/feed/feed_news_rss.asp",
        "country": "IT",
        "priority": 7,
        "areas": [
            "Tecnologia",
            "Smartphone",
            "AI",
            "Software",
            "Gaming",
            "Guide",
        ],
    },

    {
        "name": "HDblog",
        "url": "https://www.hdblog.it/feed/",
        "country": "IT",
        "priority": 8,
        "areas": [
            "Tecnologia",
            "Smartphone",
            "Hardware",
            "Software",
            "AI",
            "Gadget",
        ],
    },

    {
        "name": "SmartWorld",
        "url": "https://www.smartworld.it/feed",
        "country": "IT",
        "priority": 7,
        "areas": [
            "Tecnologia",
            "Smartphone",
            "App",
            "Software",
            "Guide",
            "Servizi",
        ],
    },

    {
        "name": "Multiplayer.it",
        "url": "https://psapp.multiplayer.it/feed/",
        "country": "IT",
        "priority": 6,
        "areas": [
            "Tecnologia",
            "Gaming",
            "Hardware",
            "Console",
            "AI",
        ],
    },


    # ========================================================
    # 🌍 FONTI INTERNAZIONALI
    # ========================================================

    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "country": "INT",
        "priority": 9,
        "areas": [
            "News",
            "AI",
            "Startup",
            "Tecnologia",
        ],
    },

    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "country": "INT",
        "priority": 9,
        "areas": [
            "Tecnologia",
            "AI",
            "Hardware",
            "Software",
        ],
    },

    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "country": "INT",
        "priority": 9,
        "areas": [
            "Tecnologia",
            "AI",
            "Sicurezza",
            "Scienza",
        ],
    },

    {
        "name": "BleepingComputer",
        "url": "https://www.bleepingcomputer.com/feed/",
        "country": "INT",
        "priority": 9,
        "areas": [
            "Sicurezza",
            "Tecnologia",
            "Guide",
        ],
    },

    {
        "name": "The Register",
        "url": "https://www.theregister.com/headlines.atom",
        "country": "INT",
        "priority": 8,
        "areas": [
            "Tecnologia",
            "AI",
            "Sicurezza",
            "Cloud",
        ],
    },

    {
        "name": "OpenAI",
        "url": "https://openai.com/news/rss.xml",
        "country": "INT",
        "priority": 10,
        "areas": [
            "AI",
        ],
    },

    {
        "name": "Google AI",
        "url": "https://blog.google/technology/ai/rss/",
        "country": "INT",
        "priority": 10,
        "areas": [
            "AI",
        ],
    },
]


# ============================================================
# PULIZIA TESTO
# ============================================================

def clean_text(value: str) -> str:

    if not value:
        return ""

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = unicodedata.normalize(
        "NFKC",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ============================================================
# NORMALIZZAZIONE TITOLI
# ============================================================

def normalize_title(title: str) -> str:

    title = clean_text(title).lower()

    title = re.sub(
        r"\b(update|breaking|news|exclusive|report)\b",
        " ",
        title,
    )

    title = re.sub(
        r"[^a-z0-9àèéìòù\s]",
        " ",
        title,
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip()


def title_tokens(title: str) -> set[str]:

    words = normalize_title(
        title
    ).split()

    stopwords = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "is",
        "are",
        "with",
        "new",
        "di",
        "il",
        "la",
        "lo",
        "le",
        "un",
        "una",
        "e",
        "per",
        "con",
        "su",
    }

    return {
        word
        for word in words
        if len(word) >= 3
        and word not in stopwords
    }


# ============================================================
# SIMILARITÀ TITOLI
# ============================================================

def title_similarity(
    title_a: str,
    title_b: str,
) -> float:

    a = normalize_title(title_a)
    b = normalize_title(title_b)

    if not a or not b:
        return 0.0

    sequence_score = SequenceMatcher(
        None,
        a,
        b,
    ).ratio()

    tokens_a = title_tokens(
        title_a
    )

    tokens_b = title_tokens(
        title_b
    )

    if tokens_a and tokens_b:

        intersection = len(
            tokens_a & tokens_b
        )

        union = len(
            tokens_a | tokens_b
        )

        jaccard_score = (
            intersection / union
        )

    else:

        jaccard_score = 0.0

    return (
        sequence_score * 0.45
        + jaccard_score * 0.55
    )


# ============================================================
# ID ARTICOLO
# ============================================================

def make_id(
    title: str,
    url: str,
) -> str:

    raw = (
        normalize_title(title)
        + "|"
        + url.strip().lower()
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:16]


# ============================================================
# DATA
# ============================================================

def parse_date(entry):

    for field in (
        "published_parsed",
        "updated_parsed",
        "created_parsed",
    ):

        value = getattr(
            entry,
            field,
            None,
        )

        if value:

            try:

                return datetime(
                    value.tm_year,
                    value.tm_mon,
                    value.tm_mday,
                    value.tm_hour,
                    value.tm_min,
                    value.tm_sec,
                    tzinfo=timezone.utc,
                )

            except Exception:
                pass

    return None


# ============================================================
# IMMAGINE
# ============================================================

def get_image(entry) -> str:

    media_content = getattr(
        entry,
        "media_content",
        [],
    )

    if media_content:

        for media in media_content:

            url = media.get(
                "url"
            )

            if url:
                return url

    media_thumbnail = getattr(
        entry,
        "media_thumbnail",
        [],
    )

    if media_thumbnail:

        for media in media_thumbnail:

            url = media.get(
                "url"
            )

            if url:
                return url

    for enclosure in getattr(
        entry,
        "enclosures",
        [],
    ):

        url = (
            enclosure.get("href")
            or enclosure.get("url")
        )

        if url:
            return url

    return ""


# ============================================================
# RACCOLTA FEED
# ============================================================

def collect_feed(
    feed_config: dict,
) -> list[dict]:

    name = feed_config[
        "name"
    ]

    url = feed_config[
        "url"
    ]

    print("")
    print(
        f"[RSS] {name}"
    )

    print(
        f"      {url}"
    )

    try:

        feed = feedparser.parse(
            url
        )

    except Exception as exc:

        print(
            f"      ERRORE: {exc}"
        )

        return []

    if getattr(
        feed,
        "bozo",
        False,
    ):

        print(
            "      Avviso feed: "
            f"{getattr(feed, 'bozo_exception', '')}"
        )

    entries = getattr(
        feed,
        "entries",
        [],
    )

    if not entries:

        print(
            "      Articoli validi: 0"
        )

        return []

    now = datetime.now(
        timezone.utc
    )

    cutoff = (
        now
        - timedelta(
            hours=MAX_AGE_HOURS
        )
    )

    items = []

    for entry in entries[
        :MAX_ITEMS_PER_FEED
    ]:

        title = clean_text(
            entry.get(
                "title",
                "",
            )
        )

        link = (
            entry.get(
                "link",
                "",
            )
            .strip()
        )

        description = clean_text(
            entry.get(
                "summary",
                entry.get(
                    "description",
                    "",
                ),
            )
        )

        if not title or not link:
            continue

        published = parse_date(
            entry
        )

        if (
            published
            and published < cutoff
        ):
            continue

        item = {

            "id": make_id(
                title,
                link,
            ),

            "title": title,

            "url": link,

            "description": description[
                :4000
            ],

            "image": get_image(
                entry
            ),

            "source": name,

            "source_domain": urlparse(
                link
            ).netloc,

            "source_country": feed_config[
                "country"
            ],

            "source_priority": feed_config[
                "priority"
            ],

            "areas": feed_config[
                "areas"
            ],

            "published_at": (
                published.isoformat()
                if published
                else ""
            ),
        }

        items.append(
            item
        )

    print(
        f"      Articoli validi: "
        f"{len(items)}"
    )

    return items


# ============================================================
# DUPLICATI ESATTI
# ============================================================

def remove_exact_duplicates(
    items: list[dict],
) -> list[dict]:

    seen_urls = set()

    seen_titles = set()

    result = []

    for item in items:

        normalized_url = (
            item["url"]
            .split("#")[0]
            .rstrip("/")
            .lower()
        )

        normalized_title = normalize_title(
            item["title"]
        )

        if normalized_url in seen_urls:
            continue

        if normalized_title in seen_titles:
            continue

        seen_urls.add(
            normalized_url
        )

        seen_titles.add(
            normalized_title
        )

        result.append(
            item
        )

    return result


# ============================================================
# RAGGRUPPAMENTO STORIE
# ============================================================

def build_clusters(
    items: list[dict],
) -> list[dict]:

    clusters = []

    items = sorted(
        items,
        key=lambda item: (
            item.get(
                "source_priority",
                0,
            ),

            item.get(
                "published_at",
                "",
            ),
        ),

        reverse=True,
    )

    for item in items:

        best_cluster = None

        best_score = 0.0

        for cluster in clusters:

            representative = cluster[
                "representative"
            ]

            score = title_similarity(
                item["title"],
                representative[
                    "title"
                ],
            )

            if score > best_score:

                best_score = score

                best_cluster = (
                    cluster
                )

        if (
            best_cluster is not None
            and best_score
            >= TITLE_SIMILARITY_THRESHOLD
        ):

            best_cluster[
                "items"
            ].append(
                item
            )

            if (
                item[
                    "source_priority"
                ]
                >
                best_cluster[
                    "representative"
                ][
                    "source_priority"
                ]
            ):

                best_cluster[
                    "representative"
                ] = item

        else:

            clusters.append(
                {
                    "cluster_id": (
                        f"story-"
                        f"{len(clusters) + 1:04d}"
                    ),

                    "representative": item,

                    "items": [
                        item
                    ],
                }
            )

    return clusters


# ============================================================
# PREPARAZIONE PER GEMINI
# ============================================================

def prepare_for_ai(
    clusters: list[dict],
) -> list[dict]:

    prepared = []

    for cluster in clusters:

        representative = cluster[
            "representative"
        ]

        sources = []

        for item in cluster[
            "items"
        ]:

            sources.append(
                {
                    "source": item[
                        "source"
                    ],

                    "url": item[
                        "url"
                    ],

                    "title": item[
                        "title"
                    ],

                    "description": item[
                        "description"
                    ],

                    "published_at": item[
                        "published_at"
                    ],
                }
            )

        prepared.append(
            {
                "cluster_id": cluster[
                    "cluster_id"
                ],

                "title": representative[
                    "title"
                ],

                "url": representative[
                    "url"
                ],

                "description": representative[
                    "description"
                ],

                "image": representative[
                    "image"
                ],

                "source": representative[
                    "source"
                ],

                "source_domain": representative[
                    "source_domain"
                ],

                "source_country": representative[
                    "source_country"
                ],

                "areas": representative[
                    "areas"
                ],

                "published_at": representative[
                    "published_at"
                ],

                "source_count": len(
                    sources
                ),

                "sources": sources,
            }
        )

    prepared.sort(
        key=lambda item: (
            item[
                "source_count"
            ],

            item[
                "published_at"
            ],
        ),

        reverse=True,
    )

    return prepared[
        :MAX_GEMINI_CLUSTERS
    ]


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("=" * 65)
    print(
        "       AI VISION - RSS COLLECTOR 2.0"
    )
    print("=" * 65)

    all_items = []

    for feed_config in FEEDS:

        items = collect_feed(
            feed_config
        )

        all_items.extend(
            items
        )

    print("")
    print("-" * 65)

    print(
        "Articoli raccolti: "
        f"{len(all_items)}"
    )

    all_items = all_items[
        :MAX_TOTAL_RAW_ITEMS
    ]

    # --------------------------------------------------------
    # DUPLICATI ESATTI
    # --------------------------------------------------------

    unique_items = (
        remove_exact_duplicates(
            all_items
        )
    )

    print(
        "Dopo duplicati esatti: "
        f"{len(unique_items)}"
    )

    # --------------------------------------------------------
    # CLUSTER
    # --------------------------------------------------------

    clusters = build_clusters(
        unique_items
    )

    print(
        "Storie raggruppate: "
        f"{len(clusters)}"
    )

    # --------------------------------------------------------
    # PREPARAZIONE GEMINI
    # --------------------------------------------------------

    ai_items = prepare_for_ai(
        clusters
    )

    print(
        "Storie passate a Gemini: "
        f"{len(ai_items)}"
    )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "collector_version": "2.0",

        "statistics": {

            "raw_items": len(
                all_items
            ),

            "unique_items": len(
                unique_items
            ),

            "clusters": len(
                clusters
            ),

            "sent_to_ai": len(
                ai_items
            ),
        },

        "items": ai_items,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("")
    print("=" * 65)
    print(
        "             RACCOLTA COMPLETATA"
    )
    print("=" * 65)

    print(
        f"File creato: {OUTPUT_FILE}"
    )

    print("")


if __name__ == "__main__":
    main()
