#!/usr/bin/env python3

import os
import re
import json
import time
import hashlib
import difflib
import unicodedata
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict

import feedparser


# ============================================================
# RSS COLLECTOR 2.4
# ============================================================

VERSION = "2.4"

MAX_AGE_HOURS = 48
MAX_ITEMS_PER_FEED = 25
MAX_TOTAL_ITEMS = 300

MAX_GEMINI_STORIES = 80
MAX_ITEMS_PER_SOURCE = 12
MAX_AI_STORIES = 18

CLUSTER_THRESHOLD = 0.40

OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "rss_output.json")


# ============================================================
# RSS SOURCES
# ============================================================

FEEDS = [
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "priority": 3,
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "priority": 3,
    },
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "priority": 3,
    },
    {
        "name": "BleepingComputer",
        "url": "https://www.bleepingcomputer.com/feed/",
        "priority": 3,
    },
    {
        "name": "The Register",
        "url": "https://www.theregister.com/headlines.atom",
        "priority": 2,
    },
    {
        "name": "OpenAI",
        "url": "https://openai.com/news/rss.xml",
        "priority": 2,
    },
    {
        "name": "Google AI",
        "url": "https://blog.google/technology/ai/rss/",
        "priority": 2,
    },
    {
        "name": "Hardware Upgrade",
        "url": "https://www.hwupgrade.it/rss.xml",
        "priority": 2,
    },
    {
        "name": "Tom's Hardware Italia",
        "url": "https://www.tomshw.it/feed/",
        "priority": 3,
    },
    {
        "name": "DDay",
        "url": "https://www.dday.it/redazione/rss",
        "priority": 2,
    },
    {
        "name": "Everyeye Tech",
        "url": "https://www.everyeye.it/rss.xml",
        "priority": 2,
    },
    {
        "name": "HDblog",
        "url": "https://www.hdblog.it/feed/",
        "priority": 3,
    },
    {
        "name": "SmartWorld",
        "url": "https://www.smartworld.it/feed",
        "priority": 3,
    },
    {
        "name": "Multiplayer.it",
        "url": "https://multiplayer.it/feed/",
        "priority": 2,
    },
]


# ============================================================
# TAXONOMY
# ============================================================

CATEGORIES = [
    "Smartphone & Mobile",
    "PC & Hardware",
    "Gaming",
    "Software & App",
    "AI",
    "Sicurezza",
    "Gadget & Consumer Tech",
    "Streaming & Entertainment",
    "Offerte & Prezzi",
    "Tecnologia",
]


CATEGORY_KEYWORDS = {
    "Smartphone & Mobile": [
        "smartphone",
        "telefono",
        "cellulare",
        "android",
        "iphone",
        "ios",
        "pixel",
        "galaxy",
        "oneplus",
        "xiaomi",
        "oppo",
        "honor",
        "motorola",
        "realme",
        "samsung",
        "tablet",
        "ipad",
        "watch",
        "smartwatch",
        "wearable",
        "mobile",
        "5g",
        "4g",
        "esim",
        "app store",
        "google play",
    ],

    "PC & Hardware": [
        "pc",
        "computer",
        "laptop",
        "notebook",
        "desktop",
        "cpu",
        "gpu",
        "processore",
        "scheda video",
        "scheda madre",
        "ram",
        "ssd",
        "hard disk",
        "monitor",
        "display",
        "intel",
        "amd",
        "nvidia",
        "radeon",
        "geforce",
        "rtx",
        "ryzen",
        "snapdragon",
        "qualcomm",
        "hardware",
        "windows pc",
        "mini pc",
        "gaming pc",
        "periferiche",
        "tastiera",
        "mouse",
        "webcam",
        "stampante",
    ],

    "Gaming": [
        "videogioco",
        "videogiochi",
        "gaming",
        "game",
        "playstation",
        "ps5",
        "ps4",
        "xbox",
        "nintendo",
        "switch",
        "switch 2",
        "steam",
        "epic games",
        "gta",
        "fortnite",
        "minecraft",
        "console",
        "controller",
        "gamepad",
        "esports",
    ],

    "Software & App": [
        "software",
        "app",
        "applicazione",
        "programma",
        "browser",
        "chrome",
        "edge",
        "firefox",
        "windows",
        "macos",
        "linux",
        "android app",
        "ios app",
        "microsoft 365",
        "office",
        "whatsapp",
        "telegram",
        "zoom",
        "slack",
        "discord",
        "dropbox",
        "onedrive",
        "google drive",
    ],

    "AI": [
        "intelligenza artificiale",
        "artificial intelligence",
        "generative ai",
        "genai",
        "machine learning",
        "deep learning",
        "chatgpt",
        "openai",
        "gemini",
        "google ai",
        "claude",
        "anthropic",
        "copilot",
        "llm",
        "modello linguistico",
        "ai agent",
        "agente ai",
        "generative",
        "generazione immagini",
        "generazione video",
        "prompt",
        "chatbot",
    ],

    "Sicurezza": [
        "sicurezza",
        "cybersecurity",
        "cyber security",
        "hacker",
        "hacking",
        "malware",
        "ransomware",
        "phishing",
        "truffa",
        "truffe",
        "vulnerabilità",
        "vulnerability",
        "exploit",
        "attacco informatico",
        "data breach",
        "violazione",
        "furto dati",
        "password",
        "account rubati",
        "privacy",
        "spyware",
        "trojan",
        "virus",
        "botnet",
    ],

    "Gadget & Consumer Tech": [
        "gadget",
        "smart home",
        "domotica",
        "telecamera",
        "videocamera",
        "cuffie",
        "auricolari",
        "earbuds",
        "speaker",
        "altoparlante",
        "lampada smart",
        "smart tv",
        "tv",
        "televisore",
        "robot",
        "aspirapolvere",
        "powerbank",
        "caricatore",
        "hub",
        "router",
        "dispositivo",
        "device",
        "accessorio",
    ],

    "Streaming & Entertainment": [
        "netflix",
        "prime video",
        "disney+",
        "disney plus",
        "hbo",
        "max",
        "paramount",
        "streaming",
        "serie tv",
        "serie televisiva",
        "film",
        "cinema",
        "youtube",
        "spotify",
        "musica",
        "podcast",
    ],

    "Offerte & Prezzi": [
        "offerta",
        "offerte",
        "sconto",
        "sconti",
        "prezzo",
        "prezzi",
        "promozione",
        "promozioni",
        "coupon",
        "buono",
        "voucher",
        "ribasso",
        "in offerta",
        "super offerta",
        "amazon",
        "mediaworld",
        "unieuro",
        "eprice",
        "ebay",
    ],
}


# ============================================================
# STORY TYPES
# ============================================================

STORY_TYPES = [
    "OFFERTA",
    "RECENSIONE",
    "GUIDA",
    "SICUREZZA",
    "RUMOR",
    "SCIENZA",
    "ANALISI",
    "AZIENDALE",
    "NEWS",
]


STORY_TYPE_KEYWORDS = {
    "OFFERTA": [
        "offerta",
        "sconto",
        "scontato",
        "promozione",
        "promozioni",
        "coupon",
        "voucher",
        "prezzo",
        "prezzi",
        "ribasso",
        "in offerta",
        "amazon",
        "unieuro",
        "mediaworld",
    ],

    "RECENSIONE": [
        "recensione",
        "review",
        "test",
        "prova",
        "abbiamo provato",
        "provato",
        "hands-on",
        "verdetto",
    ],

    "GUIDA": [
        "come fare",
        "come usare",
        "come attivare",
        "come disattivare",
        "come installare",
        "guida",
        "tutorial",
        "come funziona",
        "passo passo",
        "step by step",
    ],

    "SICUREZZA": [
        "vulnerabilità",
        "vulnerability",
        "malware",
        "ransomware",
        "phishing",
        "hacker",
        "hacking",
        "cybersecurity",
        "cyber security",
        "data breach",
        "violazione",
        "attacco informatico",
        "exploit",
        "furto dati",
        "password",
        "spyware",
        "trojan",
    ],

    "RUMOR": [
        "rumor",
        "rumour",
        "indiscrezione",
        "indiscrezioni",
        "secondo indiscrezioni",
        "potrebbe",
        "si dice",
        "leak",
        "leaked",
        "anticipazione",
        "anticipazioni",
        "presunto",
        "presunte",
    ],

    "SCIENZA": [
        "ricerca",
        "ricercatori",
        "studio",
        "scientifico",
        "scienza",
        "laboratorio",
        "università",
        "università",
        "esperimento",
        "esperimenti",
        "fisica",
        "biologia",
        "spazio",
        "nasa",
    ],

    "ANALISI": [
        "analisi",
        "approfondimento",
        "perché",
        "perche",
        "confronto",
        "confrontiamo",
        "analizzato",
        "analizzando",
    ],

    "AZIENDALE": [
        "azienda",
        "azienda annuncia",
        "annuncia",
        "annunciato",
        "ceo",
        "dirigente",
        "investimento",
        "investimenti",
        "acquisizione",
        "acquisizioni",
        "partnership",
        "accordo",
        "ricavi",
        "fatturato",
        "profitti",
        "licenziamenti",
        "dipendenti",
        "mercato",
        "quotazione",
        "azioni",
    ],
}


# ============================================================
# ENTITY KEYWORDS
# ============================================================

ENTITIES = [
    "OpenAI",
    "Anthropic",
    "Microsoft",
    "Google",
    "Apple",
    "Samsung",
    "Amazon",
    "Meta",
    "Nvidia",
    "AMD",
    "Intel",
    "Qualcomm",
    "OnePlus",
    "Xiaomi",
    "Oppo",
    "Honor",
    "Sony",
    "Nintendo",
    "Lenovo",
    "Dell",
    "HP",
    "Asus",
    "Acer",
    "Huawei",
    "Motorola",
    "PlayStation",
    "Xbox",
    "Nintendo Switch",
    "Switch 2",
    "PS5",
    "iPhone",
    "iPad",
    "Galaxy",
    "Pixel",
    "Windows",
    "macOS",
    "Linux",
    "ChatGPT",
    "Gemini",
    "Claude",
    "Copilot",
    "Android",
    "iOS",
    "Chrome",
    "Firefox",
    "Edge",
    "Steam",
    "Netflix",
    "YouTube",
    "Spotify",
]


# ============================================================
# COMMERCIAL / PRACTICAL KEYWORDS
# ============================================================

COMMERCIAL_KEYWORDS = [
    "offerta",
    "sconto",
    "prezzo",
    "prezzi",
    "coupon",
    "voucher",
    "acquistare",
    "acquisto",
    "comprare",
    "in vendita",
    "disponibile",
    "disponibilità",
    "lancio",
    "uscita",
    "nuovo",
    "nuova",
    "nuovi",
    "nuove",
    "modello",
    "smartphone",
    "laptop",
    "pc",
    "tablet",
    "tv",
    "monitor",
    "cuffie",
    "auricolari",
    "console",
    "app",
    "software",
    "servizio",
    "servizi",
]


PRACTICAL_KEYWORDS = [
    "come",
    "guida",
    "tutorial",
    "configurare",
    "configurazione",
    "installare",
    "installazione",
    "aggiornare",
    "aggiornamento",
    "attivare",
    "disattivare",
    "risolvere",
    "problema",
    "problemi",
    "funziona",
    "funzionamento",
    "utilizzare",
    "usare",
    "impostazioni",
    "impostazione",
    "consigli",
    "consiglio",
    "confronto",
]


USER_FOCUSED_KEYWORDS = [
    "utenti",
    "utente",
    "clienti",
    "consumatori",
    "possessori",
    "proprietari",
    "chi usa",
    "chi utilizza",
    "per chi",
    "come",
    "problema",
    "problemi",
    "novità",
    "novità per",
    "disponibile",
]


LOW_VALUE_KEYWORDS = [
    "earnings",
    "quarterly results",
    "revenue",
    "fatturato",
    "ricavi",
    "profitti",
    "profitto",
    "azioni",
    "stock",
    "borsa",
    "investitori",
    "investimento",
    "investimenti",
    "finanziamento",
    "funding",
    "valuation",
    "valutazione aziendale",
]


CORPORATE_KEYWORDS = [
    "ceo",
    "chief executive",
    "presidente",
    "dirigente",
    "executive",
    "partnership",
    "acquisizione",
    "acquisizioni",
    "fusione",
    "accordo commerciale",
    "accordo",
    "investimento",
    "investimenti",
    "licenziamenti",
    "dipendenti",
    "fatturato",
    "ricavi",
    "profitti",
    "trimestrale",
    "quarter",
]


# ============================================================
# CATEGORY COMPATIBILITY
# ============================================================

COMPATIBLE_CATEGORY_PAIRS = {
    frozenset(["Software & App", "PC & Hardware"]),
    frozenset(["Smartphone & Mobile", "Software & App"]),
    frozenset(["AI", "Software & App"]),
    frozenset(["AI", "Tecnologia"]),
    frozenset(["PC & Hardware", "Tecnologia"]),
    frozenset(["Gadget & Consumer Tech", "Tecnologia"]),
    frozenset(["Gaming", "PC & Hardware"]),
    frozenset(["Streaming & Entertainment", "Software & App"]),
}


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def normalize_text(text):
    if not text:
        return ""

    text = str(text)

    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    text = text.lower()

    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9àèéìòùü+#.\- ]+", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tokenize(text):
    text = normalize_text(text)

    if not text:
        return set()

    words = text.split()

    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "have",
        "has",
        "are",
        "was",
        "were",
        "will",
        "your",
        "you",
        "how",
        "what",
        "why",
        "when",
        "where",
        "their",
        "they",
        "into",
        "about",
        "after",
        "before",
        "than",
        "then",
        "also",
        "more",
        "most",
        "new",
        "news",
        "its",
        "our",
        "per",
        "con",
        "del",
        "della",
        "delle",
        "degli",
        "dei",
        "una",
        "uno",
        "un",
        "che",
        "come",
        "sono",
        "dopo",
        "prima",
        "sul",
        "sulla",
        "sulle",
        "nel",
        "nella",
        "nelle",
        "gli",
        "le",
        "i",
        "il",
        "di",
        "da",
        "a",
        "e",
        "o",
        "in",
        "su",
    }

    return {
        word
        for word in words
        if len(word) > 2 and word not in stopwords
    }


def keyword_set(text):
    return tokenize(text)


def jaccard_similarity(set_a, set_b):
    if not set_a or not set_b:
        return 0.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    if union == 0:
        return 0.0

    return intersection / union


def sequence_similarity(text_a, text_b):
    if not text_a or not text_b:
        return 0.0

    return difflib.SequenceMatcher(
        None,
        normalize_text(text_a),
        normalize_text(text_b)
    ).ratio()


def contains_any(text, keywords):
    normalized = normalize_text(text)

    return any(
        normalize_text(keyword) in normalized
        for keyword in keywords
    )


def count_keywords(text, keywords):
    normalized = normalize_text(text)

    return sum(
        1
        for keyword in keywords
        if normalize_text(keyword) in normalized
    )


def extract_entities(text):
    normalized = normalize_text(text)

    found = set()

    for entity in ENTITIES:
        normalized_entity = normalize_text(entity)

        if normalized_entity in normalized:
            found.add(entity)

    return found


def make_hash(text):
    return hashlib.sha256(
        normalize_text(text).encode("utf-8")
    ).hexdigest()


def parse_datetime(entry):
    value = None

    if getattr(entry, "published_parsed", None):
        value = entry.published_parsed

    elif getattr(entry, "updated_parsed", None):
        value = entry.updated_parsed

    if value:
        try:
            from calendar import timegm

            return datetime.fromtimestamp(
                timegm(value),
                tz=timezone.utc
            )
        except Exception:
            pass

    return datetime.now(timezone.utc)


def clean_html(text):
    if not text:
        return ""

    text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_entry_description(entry):
    description = ""

    if getattr(entry, "summary", None):
        description = entry.summary

    elif getattr(entry, "description", None):
        description = entry.description

    elif getattr(entry, "content", None):
        try:
            description = entry.content[0].value
        except Exception:
            description = ""

    return clean_html(description)


def get_entry_image(entry):
    image = ""

    if getattr(entry, "media_content", None):
        try:
            image = entry.media_content[0].get("url", "")
        except Exception:
            pass

    if not image and getattr(entry, "media_thumbnail", None):
        try:
            image = entry.media_thumbnail[0].get("url", "")
        except Exception:
            pass

    if not image:
        for link in getattr(entry, "links", []):
            href = link.get("href", "")
            link_type = link.get("type", "")

            if (
                "image" in link_type
                or href.lower().endswith(
                    (".jpg", ".jpeg", ".png", ".webp")
                )
            ):
                image = href
                break

    return image


# ============================================================
# CATEGORY CLASSIFICATION
# ============================================================

def classify_category(title, description, source=""):
    text = f"{title} {description} {source}"

    scores = {
        category: 0
        for category in CATEGORIES
    }

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if normalize_text(keyword) in normalize_text(text):
                scores[category] += 1

    # Strong explicit signals
    normalized = normalize_text(text)

    if any(
        x in normalized
        for x in [
            "chatgpt",
            "gemini",
            "claude",
            "openai",
            "anthropic",
            "copilot",
            "intelligenza artificiale",
            "artificial intelligence",
            "generative ai",
        ]
    ):
        scores["AI"] += 3

    if any(
        x in normalized
        for x in [
            "ransomware",
            "malware",
            "phishing",
            "vulnerabilita",
            "data breach",
            "cybersecurity",
            "cyber security",
            "attacco informatico",
        ]
    ):
        scores["Sicurezza"] += 4

    if any(
        x in normalized
        for x in [
            "ps5",
            "playstation",
            "xbox",
            "nintendo switch",
            "switch 2",
            "videogioco",
            "gaming",
        ]
    ):
        scores["Gaming"] += 3

    if any(
        x in normalized
        for x in [
            "offerta",
            "sconto",
            "coupon",
            "voucher",
            "in offerta",
        ]
    ):
        scores["Offerte & Prezzi"] += 3

    # Source-specific hints
    source_normalized = normalize_text(source)

    if "bleepingcomputer" in source_normalized:
        scores["Sicurezza"] += 4

    if "tom s hardware" in source_normalized:
        scores["PC & Hardware"] += 2

    if "smartworld" in source_normalized:
        scores["Smartphone & Mobile"] += 1

    if "hdblog" in source_normalized:
        scores["Smartphone & Mobile"] += 1

    if "multiplayer" in source_normalized:
        scores["Gaming"] += 4

    if "openai" in source_normalized:
        scores["AI"] += 3

    if "google ai" in source_normalized:
        scores["AI"] += 3

    best_category = max(
        scores,
        key=scores.get
    )

    if scores[best_category] == 0:
        return "Tecnologia"

    return best_category


# ============================================================
# STORY TYPE CLASSIFICATION
# ============================================================

def classify_story_type(title, description):
    text = f"{title} {description}"

    # Priority intentionally matters.
    # Security must be identified before rumor/leak.
    priority_order = [
        "SICUREZZA",
        "OFFERTA",
        "GUIDA",
        "RECENSIONE",
        "SCIENZA",
        "RUMOR",
        "ANALISI",
        "AZIENDALE",
    ]

    for story_type in priority_order:
        keywords = STORY_TYPE_KEYWORDS[story_type]

        if contains_any(text, keywords):
            return story_type

    return "NEWS"


# ============================================================
# EDITORIAL SCORING
# ============================================================

def editorial_score(
    title,
    description,
    category,
    story_type,
    source,
):
    text = f"{title} {description}"

    score = 50

    commercial_count = count_keywords(
        text,
        COMMERCIAL_KEYWORDS
    )

    practical_count = count_keywords(
        text,
        PRACTICAL_KEYWORDS
    )

    user_count = count_keywords(
        text,
        USER_FOCUSED_KEYWORDS
    )

    low_value_count = count_keywords(
        text,
        LOW_VALUE_KEYWORDS
    )

    corporate_count = count_keywords(
        text,
        CORPORATE_KEYWORDS
    )

    score += min(commercial_count * 2, 20)
    score += min(practical_count * 2, 16)
    score += min(user_count * 1, 9)

    score -= min(low_value_count * 3, 25)
    score -= min(corporate_count * 2, 12)

    type_adjustments = {
        "GUIDA": 8,
        "SICUREZZA": 7,
        "RECENSIONE": 5,
        "OFFERTA": 8,
        "SCIENZA": 3,
        "ANALISI": 2,
        "RUMOR": -8,
        "AZIENDALE": -10,
        "NEWS": 0,
    }

    score += type_adjustments.get(
        story_type,
        0
    )

    source_normalized = normalize_text(source)

    if any(
        x in source_normalized
        for x in [
            "hardware",
            "bleepingcomputer",
            "ars technica",
            "tom s hardware",
        ]
    ):
        score += 4

    # AI should remain present but not dominate.
    if category == "AI":
        if (
            commercial_count == 0
            and practical_count == 0
        ):
            score -= 5

        if corporate_count > 0:
            score -= 5

    title_length = len(title)

    if title_length < 20:
        score -= 3

    if title_length > 180:
        score -= 4

    # Italian-content bonus
    italian_markers = [
        " il ",
        " la ",
        " le ",
        " gli ",
        " un ",
        " una ",
        " per ",
        " con ",
        " come ",
    ]

    normalized_title = f" {normalize_text(title)} "

    if sum(
        marker in normalized_title
        for marker in italian_markers
    ) >= 2:
        score += 2

    return max(0, min(100, score))


# ============================================================
# FEED FETCH
# ============================================================

def fetch_feed(feed_config):
    name = feed_config["name"]
    url = feed_config["url"]

    print()
    print("=" * 70)
    print(f"FEED: {name}")
    print(f"URL:  {url}")
    print("=" * 70)

    try:
        parsed = feedparser.parse(url)

        if getattr(parsed, "bozo", False):
            bozo_exception = getattr(
                parsed,
                "bozo_exception",
                None
            )

            if bozo_exception:
                print(
                    f"⚠️ Feed warning: {bozo_exception}"
                )

        entries = getattr(parsed, "entries", [])

        print(
            f"Articoli trovati: {len(entries)}"
        )

        if not entries:
            return {
                "name": name,
                "url": url,
                "status": "empty",
                "count": 0,
                "items": [],
                "error": None,
            }

        items = []

        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(hours=MAX_AGE_HOURS)
        )

        for entry in entries[:MAX_ITEMS_PER_FEED]:
            title = getattr(
                entry,
                "title",
                ""
            ).strip()

            link = getattr(
                entry,
                "link",
                ""
            ).strip()

            if not title or not link:
                continue

            description = get_entry_description(entry)

            published = parse_datetime(entry)

            if published < cutoff:
                continue

            image = get_entry_image(entry)

            category = classify_category(
                title,
                description,
                name,
            )

            story_type = classify_story_type(
                title,
                description,
            )

            score = editorial_score(
                title,
                description,
                category,
                story_type,
                name,
            )

            entities = extract_entities(
                f"{title} {description}"
            )

            item = {
                "id": make_hash(
                    f"{title}|{link}"
                )[:16],
                "title": title,
                "description": description[:1200],
                "url": link,
                "image": image,
                "source": name,
                "published": published.isoformat(),
                "category": category,
                "story_type": story_type,
                "editorial_score": score,
                "entities": sorted(
                    entities
                ),
            }

            items.append(item)

        print(
            f"Articoli validi: {len(items)}"
        )

        return {
            "name": name,
            "url": url,
            "status": "ok",
            "count": len(items),
            "items": items,
            "error": None,
        }

    except Exception as exc:
        print(
            f"❌ Errore feed {name}: {exc}"
        )

        return {
            "name": name,
            "url": url,
            "status": "error",
            "count": 0,
            "items": [],
            "error": str(exc),
        }


# ============================================================
# EXACT DEDUPLICATION
# ============================================================

def exact_deduplicate(items):
    seen_urls = set()
    seen_hashes = set()

    unique = []

    ordered = sorted(
        items,
        key=lambda x: (
            x.get("editorial_score", 0),
            x.get("published", ""),
        ),
        reverse=True,
    )

    for item in ordered:
        url = item.get("url", "")

        content_hash = make_hash(
            f"{item.get('title', '')}|"
            f"{item.get('description', '')}"
        )

        if url in seen_urls:
            continue

        if content_hash in seen_hashes:
            continue

        seen_urls.add(url)
        seen_hashes.add(content_hash)

        unique.append(item)

    return unique


# ============================================================
# CLUSTERING
# ============================================================

def categories_compatible(category_a, category_b):
    if category_a == category_b:
        return True

    pair = frozenset(
        [category_a, category_b]
    )

    return pair in COMPATIBLE_CATEGORY_PAIRS


def article_similarity(item_a, item_b):
    category_a = item_a.get(
        "category",
        "Tecnologia"
    )

    category_b = item_b.get(
        "category",
        "Tecnologia"
    )

    if not categories_compatible(
        category_a,
        category_b,
    ):
        return 0.0

    title_a = item_a.get("title", "")
    title_b = item_b.get("title", "")

    desc_a = item_a.get(
        "description",
        ""
    )

    desc_b = item_b.get(
        "description",
        ""
    )

    title_seq = sequence_similarity(
        title_a,
        title_b,
    )

    title_keywords = jaccard_similarity(
        keyword_set(title_a),
        keyword_set(title_b),
    )

    description_keywords = jaccard_similarity(
        keyword_set(desc_a),
        keyword_set(desc_b),
    )

    combined_a = (
        f"{title_a} {desc_a}"
    )

    combined_b = (
        f"{title_b} {desc_b}"
    )

    combined_keywords = jaccard_similarity(
        keyword_set(combined_a),
        keyword_set(combined_b),
    )

    entities_a = set(
        item_a.get("entities", [])
    )

    entities_b = set(
        item_b.get("entities", [])
    )

    entity_overlap = jaccard_similarity(
        entities_a,
        entities_b,
    )

    score = (
        title_seq * 0.25
        + title_keywords * 0.25
        + description_keywords * 0.10
        + combined_keywords * 0.15
        + entity_overlap * 0.25
    )

    shared_entities = (
        entities_a & entities_b
    )

    if shared_entities:
        score += 0.05

    shared_title_keywords = (
        keyword_set(title_a)
        & keyword_set(title_b)
    )

    if len(shared_title_keywords) >= 3:
        score += 0.05

    return min(score, 1.0)


class UnionFind:
    def __init__(self, size):
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value):
        while self.parent[value] != value:
            self.parent[value] = (
                self.parent[
                    self.parent[value]
                ]
            )
            value = self.parent[value]

        return value

    def union(self, a, b):
        root_a = self.find(a)
        root_b = self.find(b)

        if root_a == root_b:
            return

        if self.rank[root_a] < self.rank[root_b]:
            self.parent[root_a] = root_b

        elif self.rank[root_a] > self.rank[root_b]:
            self.parent[root_b] = root_a

        else:
            self.parent[root_b] = root_a
            self.rank[root_a] += 1


def cluster_articles(items):
    total = len(items)

    if total == 0:
        return []

    uf = UnionFind(total)

    comparisons = 0
    possible_links = 0

    for i in range(total):
        for j in range(i + 1, total):
            comparisons += 1

            similarity = article_similarity(
                items[i],
                items[j],
            )

            if similarity >= CLUSTER_THRESHOLD:
                uf.union(i, j)
                possible_links += 1

    groups = defaultdict(list)

    for index in range(total):
        root = uf.find(index)
        groups[root].append(
            items[index]
        )

    clusters = []

    for cluster_index, group in enumerate(
        groups.values(),
        start=1,
    ):
        group = sorted(
            group,
            key=lambda x: (
                x.get(
                    "editorial_score",
                    0
                ),
                x.get(
                    "published",
                    ""
                ),
            ),
            reverse=True,
        )

        representative = group[0]

        sources = sorted(
            {
                item.get(
                    "source",
                    ""
                )
                for item in group
            }
        )

        categories = Counter(
            item.get(
                "category",
                "Tecnologia"
            )
            for item in group
        )

        story_types = Counter(
            item.get(
                "story_type",
                "NEWS"
            )
            for item in group
        )

        representative = dict(
            representative
        )

        representative["cluster_id"] = (
            f"cluster_{cluster_index:04d}"
        )

        representative[
            "source_count"
        ] = len(sources)

        representative[
            "article_count"
        ] = len(group)

        representative[
            "sources"
        ] = sources

        representative[
            "cluster_categories"
        ] = dict(categories)

        representative[
            "cluster_story_types"
        ] = dict(story_types)

        representative[
            "cluster_articles"
        ] = [
            {
                "title": article.get(
                    "title",
                    ""
                ),
                "source": article.get(
                    "source",
                    ""
                ),
                "url": article.get(
                    "url",
                    ""
                ),
            }
            for article in group
        ]

        clusters.append(
            representative
        )

    print()
    print(
        f"Clustering: {comparisons:,} confronti, "
        f"{possible_links} collegamenti, "
        f"{len(clusters)} cluster"
    )

    multi_source = sum(
        1
        for cluster in clusters
        if cluster.get(
            "source_count",
            1
        ) > 1
    )

    max_cluster_size = max(
        (
            cluster.get(
                "article_count",
                1
            )
            for cluster in clusters
        ),
        default=0,
    )

    print(
        f"Cluster multi-source: {multi_source}"
    )

    print(
        f"Dimensione massima cluster: "
        f"{max_cluster_size}"
    )

    return clusters


# ============================================================
# EDITORIAL SELECTION
# ============================================================

def select_for_gemini(clusters):
    if not clusters:
        return []

    ordered = sorted(
        clusters,
        key=lambda x: (
            x.get(
                "editorial_score",
                0
            ),
            x.get(
                "source_count",
                1
            ),
            x.get(
                "article_count",
                1
            ),
            x.get(
                "published",
                ""
            ),
        ),
        reverse=True,
    )

    selected = []

    source_counter = Counter()
    category_counter = Counter()
    ai_counter = 0

    max_per_category = max(
        5,
        int(
            MAX_GEMINI_STORIES
            * 0.25
        ),
    )

    # --------------------------------------------------------
    # FIRST PASS
    # Respect category/source/AI limits
    # --------------------------------------------------------

    for cluster in ordered:
        if len(selected) >= MAX_GEMINI_STORIES:
            break

        source = cluster.get(
            "source",
            "Unknown"
        )

        category = cluster.get(
            "category",
            "Tecnologia"
        )

        if (
            source_counter[source]
            >= MAX_ITEMS_PER_SOURCE
        ):
            continue

        if (
            category_counter[category]
            >= max_per_category
        ):
            continue

        if (
            category == "AI"
            and ai_counter >= MAX_AI_STORIES
        ):
            continue

        selected.append(cluster)

        source_counter[source] += 1
        category_counter[category] += 1

        if category == "AI":
            ai_counter += 1

    # --------------------------------------------------------
    # SECOND PASS
    # Fill remaining slots while respecting source/AI
    # --------------------------------------------------------

    if len(selected) < MAX_GEMINI_STORIES:
        selected_ids = {
            item.get(
                "cluster_id"
            )
            for item in selected
        }

        for cluster in ordered:
            if len(selected) >= MAX_GEMINI_STORIES:
                break

            cluster_id = cluster.get(
                "cluster_id"
            )

            if cluster_id in selected_ids:
                continue

            source = cluster.get(
                "source",
                "Unknown"
            )

            category = cluster.get(
                "category",
                "Tecnologia"
            )

            if (
                source_counter[source]
                >= MAX_ITEMS_PER_SOURCE
            ):
                continue

            if (
                category == "AI"
                and ai_counter >= MAX_AI_STORIES
            ):
                continue

            selected.append(cluster)

            selected_ids.add(cluster_id)

            source_counter[source] += 1

            if category == "AI":
                ai_counter += 1

    return selected


# ============================================================
# PREPARE FOR GEMINI
# ============================================================

def prepare_for_gemini(items):
    prepared = []

    for index, item in enumerate(
        items,
        start=1,
    ):
        prepared.append(
            {
                "selection_order": index,

                "cluster_id": item.get(
                    "cluster_id",
                    "",
                ),

                "title": item.get(
                    "title",
                    "",
                ),

                "description": item.get(
                    "description",
                    "",
                ),

                "url": item.get(
                    "url",
                    "",
                ),

                "image": item.get(
                    "image",
                    "",
                ),

                "source": item.get(
                    "source",
                    "",
                ),

                "published": item.get(
                    "published",
                    "",
                ),

                # Collector classification
                # must be respected downstream.
                "category": item.get(
                    "category",
                    "Tecnologia",
                ),

                "story_type": item.get(
                    "story_type",
                    "NEWS",
                ),

                "editorial_score": item.get(
                    "editorial_score",
                    0,
                ),

                "source_count": item.get(
                    "source_count",
                    1,
                ),

                "article_count": item.get(
                    "article_count",
                    1,
                ),

                "sources": item.get(
                    "sources",
                    [],
                ),

                "entities": item.get(
                    "entities",
                    [],
                ),

                "cluster_articles": item.get(
                    "cluster_articles",
                    [],
                ),
            }
        )

    return prepared


# ============================================================
# STATS
# ============================================================

def build_stats(
    feed_results,
    all_items,
    unique_items,
    clusters,
    selected,
):
    category_distribution = Counter(
        item.get(
            "category",
            "Tecnologia"
        )
        for item in unique_items
    )

    story_type_distribution = Counter(
        item.get(
            "story_type",
            "NEWS"
        )
        for item in unique_items
    )

    selected_category_distribution = Counter(
        item.get(
            "category",
            "Tecnologia"
        )
        for item in selected
    )

    selected_story_type_distribution = Counter(
        item.get(
            "story_type",
            "NEWS"
        )
        for item in selected
    )

    source_distribution = Counter(
        item.get(
            "source",
            "Unknown"
        )
        for item in unique_items
    )

    multi_source_clusters = sum(
        1
        for cluster in clusters
        if cluster.get(
            "source_count",
            1
        ) > 1
    )

    return {
        "feeds_total": len(feed_results),

        "feeds_ok": sum(
            1
            for result in feed_results
            if result["status"] == "ok"
        ),

        "feeds_empty": sum(
            1
            for result in feed_results
            if result["status"] == "empty"
        ),

        "feeds_error": sum(
            1
            for result in feed_results
            if result["status"] == "error"
        ),

        "articles_collected": len(all_items),

        "articles_unique": len(unique_items),

        "exact_duplicates_removed": (
            len(all_items)
            - len(unique_items)
        ),

        "clusters": len(clusters),

        "multi_source_clusters": (
            multi_source_clusters
        ),

        "selected_for_gemini": len(
            selected
        ),

        "category_distribution": dict(
            category_distribution
        ),

        "story_type_distribution": dict(
            story_type_distribution
        ),

        "selected_category_distribution": dict(
            selected_category_distribution
        ),

        "selected_story_type_distribution": dict(
            selected_story_type_distribution
        ),

        "source_distribution": dict(
            source_distribution
        ),
    }


# ============================================================
# SAVE JSON
# ============================================================

def save_output(data):
    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(
        f"💾 Output salvato: {OUTPUT_FILE}"
    )


# ============================================================
# PRINT REPORT
# ============================================================

def print_report(
    feed_results,
    unique_items,
    clusters,
    selected,
    stats,
):
    print()
    print()
    print("#" * 70)
    print(f"RSS COLLECTOR {VERSION}")
    print("#" * 70)

    print()
    print("FEED STATUS")
    print("-" * 70)

    for result in feed_results:
        print(
            f"{result['name']:<25} "
            f"{result['status']:<8} "
            f"{result['count']:>3} articoli"
        )

        if result.get("error"):
            print(
                f"  ERRORE: {result['error']}"
            )

    print()
    print("STATISTICHE")
    print("-" * 70)

    print(
        f"Articoli raccolti: "
        f"{stats['articles_collected']}"
    )

    print(
        f"Articoli unici: "
        f"{stats['articles_unique']}"
    )

    print(
        f"Duplicati esatti rimossi: "
        f"{stats['exact_duplicates_removed']}"
    )

    print(
        f"Cluster: "
        f"{stats['clusters']}"
    )

    print(
        f"Cluster multi-source: "
        f"{stats['multi_source_clusters']}"
    )

    print(
        f"Selezionati per Gemini: "
        f"{stats['selected_for_gemini']}"
    )

    print()
    print("DISTRIBUZIONE CATEGORIE")
    print("-" * 70)

    for category, count in sorted(
        stats[
            "category_distribution"
        ].items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(
            f"{category:<30} {count:>3}"
        )

    print()
    print("DISTRIBUZIONE TIPI")
    print("-" * 70)

    for story_type, count in sorted(
        stats[
            "story_type_distribution"
        ].items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(
            f"{story_type:<30} {count:>3}"
        )

    print()
    print("SELEZIONE GEMINI - CATEGORIE")
    print("-" * 70)

    for category, count in sorted(
        stats[
            "selected_category_distribution"
        ].items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(
            f"{category:<30} {count:>3}"
        )

    print()
    print("SELEZIONE GEMINI - TIPI")
    print("-" * 70)

    for story_type, count in sorted(
        stats[
            "selected_story_type_distribution"
        ].items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(
            f"{story_type:<30} {count:>3}"
        )

    print()
    print("TOP 20 SELEZIONATI")
    print("-" * 70)

    for index, item in enumerate(
        selected[:20],
        start=1,
    ):
        print(
            f"{index:>2}. "
            f"[{item.get('editorial_score', 0):>3}] "
            f"[{item.get('category', '')}] "
            f"[{item.get('story_type', '')}] "
            f"{item.get('title', '')}"
        )

        print(
            f"    Fonte: "
            f"{item.get('source', '')}"
        )

        print(
            f"    Fonti cluster: "
            f"{', '.join(item.get('sources', []))}"
        )

    print()
    print("#" * 70)
    print(
        f"FINE RSS COLLECTOR {VERSION}"
    )
    print("#" * 70)


# ============================================================
# MAIN
# ============================================================

def main():
    start_time = time.time()

    print("#" * 70)
    print(f"AI VISION - RSS COLLECTOR {VERSION}")
    print("#" * 70)

    print()
    print(
        f"Finestra temporale: "
        f"{MAX_AGE_HOURS} ore"
    )

    print(
        f"Max articoli/feed: "
        f"{MAX_ITEMS_PER_FEED}"
    )

    print(
        f"Max articoli totali: "
        f"{MAX_TOTAL_ITEMS}"
    )

    print(
        f"Max storie Gemini: "
        f"{MAX_GEMINI_STORIES}"
    )

    # --------------------------------------------------------
    # FETCH
    # --------------------------------------------------------

    feed_results = []

    all_items = []

    for feed_config in FEEDS:
        result = fetch_feed(
            feed_config
        )

        feed_results.append(result)

        all_items.extend(
            result["items"]
        )

        if len(all_items) >= MAX_TOTAL_ITEMS:
            print(
                "⚠️ Raggiunto limite "
                "MAX_TOTAL_ITEMS."
            )
            break

    # Hard limit
    all_items = all_items[
        :MAX_TOTAL_ITEMS
    ]

    print()
    print(
        f"Totale raccolto: "
        f"{len(all_items)}"
    )

    # --------------------------------------------------------
    # EXACT DEDUPLICATION
    # --------------------------------------------------------

    unique_items = exact_deduplicate(
        all_items
    )

    print(
        f"Totale dopo deduplicazione: "
        f"{len(unique_items)}"
    )

    # --------------------------------------------------------
    # CLUSTERING
    # --------------------------------------------------------

    clusters = cluster_articles(
        unique_items
    )

    # --------------------------------------------------------
    # EDITORIAL SELECTION
    # --------------------------------------------------------

    selected = select_for_gemini(
        clusters
    )

    print()
    print(
        f"Selezionati per Gemini: "
        f"{len(selected)}"
    )

    # --------------------------------------------------------
    # PREPARE OUTPUT
    # --------------------------------------------------------

    prepared = prepare_for_gemini(
        selected
    )

    stats = build_stats(
        feed_results,
        all_items,
        unique_items,
        clusters,
        selected,
    )

    output = {
        "collector": {
            "name": "AI Vision RSS Collector",
            "version": VERSION,
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        },

        "config": {
            "max_age_hours": MAX_AGE_HOURS,
            "max_items_per_feed": MAX_ITEMS_PER_FEED,
            "max_total_items": MAX_TOTAL_ITEMS,
            "max_gemini_stories": MAX_GEMINI_STORIES,
            "max_items_per_source": MAX_ITEMS_PER_SOURCE,
            "max_ai_stories": MAX_AI_STORIES,
            "cluster_threshold": CLUSTER_THRESHOLD,
        },

        "feeds": feed_results,

        "stats": stats,

        "categories": CATEGORIES,

        "story_types": STORY_TYPES,

        "clusters": clusters,

        "items": prepared,
    }

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    save_output(output)

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    print_report(
        feed_results,
        unique_items,
        clusters,
        selected,
        stats,
    )

    elapsed = time.time() - start_time

    print()
    print(
        f"⏱️ Tempo totale: "
        f"{elapsed:.2f} secondi"
    )


if __name__ == "__main__":
    main()
