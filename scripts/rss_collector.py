import json
import hashlib
import re
import os
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher

import feedparser
import requests


# ============================================================
# AI VISION - RSS COLLECTOR 2.3
# ============================================================

VERSION = "2.3"

MAX_AGE_HOURS = 48
MAX_ITEMS_PER_FEED = 25
MAX_TOTAL_ITEMS = 300

# Numero massimo di STORIE da mandare a Gemini
MAX_GEMINI_STORIES = 80

# Limiti editoriali
MAX_ITEMS_PER_SOURCE = 12
MAX_AI_STORIES = 18

# Similarità minima per considerare due articoli
# parte della stessa storia
CLUSTER_THRESHOLD = 0.43

REQUEST_TIMEOUT = 15

USER_AGENT = f"AI-Vision-RSS-Collector/{VERSION}"


# ============================================================
# FEED
# ============================================================

FEEDS = {
    "TechCrunch": {
        "url": "https://techcrunch.com/feed/",
        "country": "USA",
        "type": "tech"
    },

    "The Verge": {
        "url": "https://www.theverge.com/rss/index.xml",
        "country": "USA",
        "type": "tech"
    },

    "Ars Technica": {
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "country": "USA",
        "type": "tech"
    },

    "BleepingComputer": {
        "url": "https://www.bleepingcomputer.com/feed/",
        "country": "USA",
        "type": "security"
    },

    "The Register": {
        "url": "https://www.theregister.com/headlines.atom",
        "country": "UK",
        "type": "tech"
    },

    "OpenAI": {
        "url": "https://openai.com/news/rss.xml",
        "country": "USA",
        "type": "ai"
    },

    "Google AI": {
        "url": "https://blog.research.google/feeds/posts/default/-/Artificial%20Intelligence",
        "country": "USA",
        "type": "ai"
    },

    "Hardware Upgrade": {
        "url": "https://www.hwupgrade.it/rss.php",
        "country": "Italia",
        "type": "hardware"
    },

    "Tom's Hardware Italia": {
        "url": "https://www.tomshw.it/feed/",
        "country": "Italia",
        "type": "hardware"
    },

    "DDay": {
        "url": "https://www.dday.it/redazione/rss",
        "country": "Italia",
        "type": "tech"
    },

    "Everyeye Tech": {
        "url": "https://tech.everyeye.it/rss/",
        "country": "Italia",
        "type": "tech"
    },

    "HDblog": {
        "url": "https://www.hdblog.it/feed/",
        "country": "Italia",
        "type": "tech"
    },

    "SmartWorld": {
        "url": "https://www.smartworld.it/feed",
        "country": "Italia",
        "type": "tech"
    },

    "Multiplayer.it": {
        "url": "https://multiplayer.it/feed/",
        "country": "Italia",
        "type": "gaming"
    }
}


# ============================================================
# CATEGORIE EDITORIALI
# ============================================================

CATEGORY_KEYWORDS = {

    "Smartphone & Mobile": [
        "iphone", "ipad", "android", "samsung galaxy", "pixel",
        "smartphone", "telefono", "cellulare", "tablet",
        "watch", "smartwatch", "wearable", "ios",
        "oneplus", "xiaomi", "motorola", "honor", "oppo",
        "realme", "vivo", "galaxy"
    ],

    "PC & Hardware": [
        "pc", "computer", "laptop", "notebook", "desktop",
        "cpu", "gpu", "processore", "scheda video",
        "nvidia", "amd", "intel", "ryzen", "radeon",
        "geforce", "ram", "ssd", "monitor", "motherboard",
        "scheda madre", "hardware", "keyboard", "mouse",
        "gaming pc"
    ],

    "Gaming": [
        "playstation", "ps5", "ps4", "xbox", "switch",
        "nintendo", "steam", "videogame", "videogioco",
        "gaming", "game", "gioco", "pc gaming",
        "minecraft", "fortnite", "elden ring", "pokemon"
    ],

    "Software & App": [
        "windows", "macos", "linux", "software", "app",
        "applicazione", "browser", "chrome", "firefox",
        "edge", "whatsapp", "telegram", "instagram",
        "facebook", "tiktok", "spotify", "office",
        "microsoft 365", "google drive", "icloud"
    ],

    "AI": [
        "intelligenza artificiale", "artificial intelligence",
        "ai", "chatgpt", "openai", "gemini", "claude",
        "copilot", "llm", "machine learning",
        "generative ai", "generative artificial intelligence",
        "modello linguistico", "deep learning"
    ],

    "Sicurezza": [
        "cybersecurity", "sicurezza informatica", "malware",
        "ransomware", "phishing", "truffa", "truffe",
        "hacker", "hacking", "vulnerabilità", "vulnerability",
        "password", "account rubato", "data breach",
        "attacco informatico", "virus", "spyware"
    ],

    "Gadget & Consumer Tech": [
        "gadget", "cuffie", "auricolari", "headset",
        "smart tv", "tv", "televisore", "speaker",
        "fotocamera", "camera", "drone", "stampante",
        "powerbank", "caricatore", "charger",
        "robot aspirapolvere", "aspirapolvere",
        "smart home", "domotica"
    ],

    "Streaming & Entertainment": [
        "netflix", "prime video", "disney+",
        "disney plus", "youtube", "streaming",
        "serie tv", "film", "cinema", "tv",
        "hbo", "max", "paramount", "apple tv"
    ],

    "Offerte & Prezzi": [
        "offerta", "offerte", "sconto", "sconti",
        "prezzo", "prezzi", "costa", "costare",
        "in offerta", "promozione", "promozioni",
        "amazon", "black friday", "prime day",
        "ribasso", "coupon", "deal"
    ],

    "Tecnologia": [
        "tecnologia", "tech", "internet", "5g", "6g",
        "fibra", "wifi", "wi-fi", "bluetooth",
        "usb", "cloud", "digitale", "rete",
        "smart home", "automotive", "auto elettrica",
        "elettrico"
    ]
}


# ============================================================
# PAROLE UTILI PER L'INTERESSE EDITORIALE
# ============================================================

COMMERCIAL_KEYWORDS = [
    "prezzo", "prezzi", "costa", "offerta", "sconto",
    "disponibile", "disponibilità", "comprare", "acquistare",
    "vendita", "uscita", "lancio", "specifiche", "specifiche tecniche",
    "specifiche", "recensione", "review", "confronto",
    "migliore", "alternativa", "vs", "versus",
    "quanto costa", "vale la pena", "pre-order",
    "preordine"
]


PRACTICAL_KEYWORDS = [
    "come fare", "come usare", "come funziona",
    "come attivare", "come disattivare", "come risolvere",
    "guida", "tutorial", "problema", "problemi",
    "soluzione", "cosa cambia", "cambiamenti",
    "nuove funzioni", "funzione", "aggiornamento",
    "aggiornamenti", "trucco", "consigli",
    "impostazioni", "impostazione"
]


LOW_VALUE_KEYWORDS = [
    "earnings", "quarterly results", "revenue",
    "ricavi", "fatturato", "utili", "azioni",
    "stock", "borsa", "investitori", "investimento",
    "funding", "finanziamento", "round",
    "acquisition", "acquisizione", "merger",
    "licenziamenti", "layoffs", "workforce",
    "ceo", "cfo"
]


CORPORATE_KEYWORDS = [
    "announces", "announced", "announcement",
    "annuncia", "annunciato", "annuncio",
    "partnership", "partnerships", "collaborazione",
    "collaborazione strategica", "press release",
    "comunicato stampa", "business",
    "enterprise", "corporate"
]


USER_FOCUSED_KEYWORDS = [
    "utenti", "utente", "clienti", "cliente",
    "consumatori", "consumer",
    "users", "user", "customers",
    "owners", "possessori",
    "dispositivi", "device"
]


# ============================================================
# STOPWORDS
# ============================================================

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this",
    "have", "has", "will", "your", "you", "are", "was",
    "sono", "della", "delle", "degli", "dello", "nella",
    "nelle", "negli", "con", "per", "una", "uno", "un",
    "gli", "che", "del", "dei", "di", "da", "in", "su",
    "come", "più", "anche", "non", "nel", "alla", "alle",
    "ai", "ad", "il", "lo", "la", "i", "le", "e", "o"
}


# ============================================================
# FUNZIONI TESTO
# ============================================================

def normalize_text(text):
    if not text:
        return ""

    text = str(text).lower()

    replacements = {
        "à": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "ò": "o",
        "ù": "u"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_keywords(text):
    text = normalize_text(text)

    words = text.split()

    return {
        word
        for word in words
        if len(word) >= 3 and word not in STOPWORDS
    }


def keyword_similarity(text_a, text_b):
    a = extract_keywords(text_a)
    b = extract_keywords(text_b)

    if not a or not b:
        return 0.0

    intersection = len(a & b)
    union = len(a | b)

    if union == 0:
        return 0.0

    return intersection / union


def text_similarity(a, b):
    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


# ============================================================
# SIMILARITÀ TRA ARTICOLI
# ============================================================

def article_similarity(item_a, item_b):

    title_a = item_a.get("title", "")
    title_b = item_b.get("title", "")

    desc_a = item_a.get("description", "")
    desc_b = item_b.get("description", "")

    title_seq = text_similarity(title_a, title_b)

    title_kw = keyword_similarity(title_a, title_b)

    desc_kw = keyword_similarity(desc_a, desc_b)

    combined_a = f"{title_a} {desc_a}"
    combined_b = f"{title_b} {desc_b}"

    combined_kw = keyword_similarity(combined_a, combined_b)

    score = (
        title_seq * 0.35 +
        title_kw * 0.35 +
        desc_kw * 0.10 +
        combined_kw * 0.20
    )

    return score


# ============================================================
# DATA
# ============================================================

def parse_date(entry):

    for field in [
        "published_parsed",
        "updated_parsed",
        "created_parsed"
    ]:

        value = getattr(entry, field, None)

        if value:
            try:
                return datetime(
                    value.tm_year,
                    value.tm_mon,
                    value.tm_mday,
                    value.tm_hour,
                    value.tm_min,
                    value.tm_sec,
                    tzinfo=timezone.utc
                )
            except Exception:
                pass

    for field in [
        "published",
        "updated",
        "created"
    ]:

        value = entry.get(field)

        if not value:
            continue

        try:
            dt = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(timezone.utc)

        except Exception:
            pass

    return None


# ============================================================
# IMAGE
# ============================================================

def get_image(entry):

    media_content = entry.get("media_content")

    if media_content:
        for media in media_content:
            url = media.get("url")

            if url:
                return url

    media_thumbnail = entry.get("media_thumbnail")

    if media_thumbnail:
        for media in media_thumbnail:
            url = media.get("url")

            if url:
                return url

    enclosures = entry.get("enclosures")

    if enclosures:
        for enclosure in enclosures:
            url = enclosure.get("href") or enclosure.get("url")

            if url:
                return url

    return None


# ============================================================
# CATEGORIA
# ============================================================

def classify_category(title, description, feed_type):

    text = normalize_text(
        f"{title} {description}"
    )

    scores = {}

    for category, keywords in CATEGORY_KEYWORDS.items():

        score = 0

        for keyword in keywords:

            keyword_normalized = normalize_text(keyword)

            if keyword_normalized in text:
                score += 1

        scores[category] = score

    best_category = max(
        scores,
        key=scores.get
    )

    best_score = scores[best_category]

    # Se non abbiamo trovato segnali specifici
    if best_score == 0:

        if feed_type == "gaming":
            return "Gaming"

        if feed_type == "security":
            return "Sicurezza"

        if feed_type == "hardware":
            return "PC & Hardware"

        if feed_type == "ai":
            return "AI"

        return "Tecnologia"

    return best_category


# ============================================================
# SCORE EDITORIALE
# ============================================================

def count_keyword_hits(text, keywords):

    text = normalize_text(text)

    return sum(
        1
        for keyword in keywords
        if normalize_text(keyword) in text
    )


def calculate_editorial_score(item):

    title = item.get("title", "")
    description = item.get("description", "")

    text = f"{title} {description}"

    category = item.get("category", "")
    feed_type = item.get("feed_type", "")

    score = 50

    # --------------------------------------------------------
    # Contenuto commerciale / utile
    # --------------------------------------------------------

    commercial_hits = count_keyword_hits(
        text,
        COMMERCIAL_KEYWORDS
    )

    practical_hits = count_keyword_hits(
        text,
        PRACTICAL_KEYWORDS
    )

    user_hits = count_keyword_hits(
        text,
        USER_FOCUSED_KEYWORDS
    )

    low_value_hits = count_keyword_hits(
        text,
        LOW_VALUE_KEYWORDS
    )

    corporate_hits = count_keyword_hits(
        text,
        CORPORATE_KEYWORDS
    )

    score += min(commercial_hits * 5, 20)
    score += min(practical_hits * 4, 16)
    score += min(user_hits * 3, 9)

    # --------------------------------------------------------
    # Penalità
    # --------------------------------------------------------

    score -= min(low_value_hits * 8, 25)
    score -= min(corporate_hits * 4, 12)

    # --------------------------------------------------------
    # Fonti specialistiche
    # --------------------------------------------------------

    if feed_type in [
        "hardware",
        "security",
        "gaming"
    ]:
        score += 4

    # --------------------------------------------------------
    # AI
    #
    # L'AI non viene esclusa.
    # Evitiamo però che qualsiasi comunicato AI
    # domini automaticamente il magazine.
    # --------------------------------------------------------

    if category == "AI":

        if commercial_hits == 0 and practical_hits == 0:
            score -= 5

        if corporate_hits > 0:
            score -= 5

    # --------------------------------------------------------
    # Titoli molto generici
    # --------------------------------------------------------

    if len(normalize_text(title).split()) < 5:
        score -= 4

    if len(normalize_text(title).split()) > 25:
        score -= 2

    # --------------------------------------------------------
    # Lingua italiana
    # --------------------------------------------------------

    italian_markers = [
        " il ", " la ", " che ", " per ",
        " una ", " con ", " come ",
        " degli ", " delle ", " dalla "
    ]

    normalized = f" {normalize_text(text)} "

    italian_hits = sum(
        1 for marker in italian_markers
        if marker in normalized
    )

    if italian_hits >= 2:
        score += 3

    return max(0, min(100, score))


# ============================================================
# URL / ID
# ============================================================

def make_id(url, title):

    value = f"{url}|{title}"

    return hashlib.sha1(
        value.encode("utf-8")
    ).hexdigest()[:16]


# ============================================================
# RACCOLTA FEED
# ============================================================

def fetch_feed(name, config):

    print(
        f"{name:<28}",
        end=" "
    )

    try:

        response = requests.get(
            config["url"],
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": USER_AGENT
            }
        )

        response.raise_for_status()

        parsed = feedparser.parse(
            response.content
        )

        if parsed.bozo and not parsed.entries:

            print(
                f"ERRORE Feed non interpretabile: "
                f"{parsed.bozo_exception}"
            )

            return None, 0

        entries = parsed.entries[:MAX_ITEMS_PER_FEED]

        print(
            f"{len(entries)} articoli"
        )

        return parsed, len(entries)

    except Exception as e:

        print(
            f"ERRORE {e}"
        )

        return None, 0


def collect_items():

    now = datetime.now(timezone.utc)

    cutoff = now - timedelta(
        hours=MAX_AGE_HOURS
    )

    all_items = []

    feed_status = {}

    print()
    print("CONTROLLO AUTOMATICO DEI FEED")
    print("-" * 46)

    for name, config in FEEDS.items():

        parsed, count = fetch_feed(
            name,
            config
        )

        if parsed is None:

            feed_status[name] = {
                "status": "error",
                "count": 0
            }

            continue

        feed_status[name] = {
            "status": "ok",
            "count": count
        }

        valid_for_feed = 0

        for entry in parsed.entries[:MAX_ITEMS_PER_FEED]:

            title = (
                entry.get("title")
                or ""
            ).strip()

            if not title:
                continue

            description = (
                entry.get("summary")
                or entry.get("description")
                or ""
            ).strip()

            url = (
                entry.get("link")
                or ""
            ).strip()

            if not url:
                continue

            published = parse_date(entry)

            # ------------------------------------------------
            # Se la data non è leggibile:
            # NON eliminiamo automaticamente l'articolo.
            #
            # Questo evita il problema visto con OpenAI,
            # Google AI e altre fonti.
            # ------------------------------------------------

            if published is not None:

                if published < cutoff:
                    continue

            item = {
                "id": make_id(
                    url,
                    title
                ),

                "title": title,

                "description": description,

                "url": url,

                "source": name,

                "country": config["country"],

                "feed_type": config["type"],

                "published": (
                    published.isoformat()
                    if published
                    else None
                ),

                "image": get_image(entry)
            }

            item["category"] = classify_category(
                title,
                description,
                config["type"]
            )

            item["editorial_score"] = calculate_editorial_score(
                item
            )

            all_items.append(item)

            valid_for_feed += 1

        print(
            f"{name:<28} "
            f"{valid_for_feed} articoli validi"
        )

    return all_items, feed_status


# ============================================================
# DEDUPLICA ESATTA
# ============================================================

def exact_deduplicate(items):

    seen_urls = set()
    seen_titles = set()

    result = []

    duplicates = 0

    # Prima gli articoli con score maggiore
    # per non dipendere dall'ordine dei feed.

    items = sorted(
        items,
        key=lambda x: (
            x.get("editorial_score", 0),
            x.get("published") or ""
        ),
        reverse=True
    )

    for item in items:

        url = item.get("url", "").strip()

        title = normalize_text(
            item.get("title", "")
        )

        if url in seen_urls:

            duplicates += 1
            continue

        if title in seen_titles:

            duplicates += 1
            continue

        seen_urls.add(url)
        seen_titles.add(title)

        result.append(item)

    return result, duplicates


# ============================================================
# CLUSTERING
# ============================================================

def build_clusters(items):

    print()
    print("CLUSTERING DELLE STORIE")
    print("-" * 46)

    if not items:
        return []

    parent = list(
        range(len(items))
    )

    def find(x):

        while parent[x] != x:

            parent[x] = parent[parent[x]]
            x = parent[x]

        return x

    def union(a, b):

        root_a = find(a)
        root_b = find(b)

        if root_a != root_b:
            parent[root_b] = root_a

    # --------------------------------------------------------
    # Confronto tra tutti gli articoli.
    #
    # MAX_TOTAL_ITEMS = 300, quindi il costo è accettabile.
    # --------------------------------------------------------

    comparisons = 0
    matches = 0

    for i in range(len(items)):

        for j in range(i + 1, len(items)):

            comparisons += 1

            score = article_similarity(
                items[i],
                items[j]
            )

            if score >= CLUSTER_THRESHOLD:

                union(i, j)
                matches += 1

    grouped = {}

    for index in range(len(items)):

        root = find(index)

        grouped.setdefault(
            root,
            []
        ).append(
            items[index]
        )

    clusters = []

    for cluster_items in grouped.values():

        # rappresentante = articolo
        # con miglior valore editoriale

        representative = max(
            cluster_items,
            key=lambda x: (
                x.get("editorial_score", 0),
                x.get("published") or ""
            )
        )

        categories = {}

        sources = {}

        for item in cluster_items:

            category = item.get(
                "category",
                "Tecnologia"
            )

            categories[category] = (
                categories.get(category, 0) + 1
            )

            source = item.get(
                "source",
                ""
            )

            sources[source] = (
                sources.get(source, 0) + 1
            )

        main_category = max(
            categories,
            key=categories.get
        )

        cluster_score = representative.get(
            "editorial_score",
            0
        )

        # Bonus per multi-source:
        # una storia confermata da più fonti
        # è più interessante per il sistema.

        if len(sources) >= 2:
            cluster_score += 5

        if len(sources) >= 3:
            cluster_score += 5

        cluster_score = min(
            100,
            cluster_score
        )

        cluster = {
            "cluster_id": hashlib.sha1(
                "|".join(
                    sorted(
                        item["id"]
                        for item in cluster_items
                    )
                ).encode("utf-8")
            ).hexdigest()[:16],

            "title": representative["title"],

            "description": representative["description"],

            "url": representative["url"],

            "image": representative.get("image"),

            "source": representative["source"],

            "published": representative.get(
                "published"
            ),

            "category": main_category,

            "editorial_score": cluster_score,

            "source_count": len(sources),

            "article_count": len(cluster_items),

            "sources": [
                {
                    "source": item["source"],
                    "title": item["title"],
                    "url": item["url"],
                    "published": item.get("published")
                }
                for item in cluster_items
            ]
        }

        clusters.append(cluster)

    multi_source = sum(
        1
        for cluster in clusters
        if cluster["source_count"] > 1
    )

    max_size = max(
        (
            cluster["article_count"]
            for cluster in clusters
        ),
        default=0
    )

    print(
        f"Confronti effettuati: {comparisons}"
    )

    print(
        f"Possibili collegamenti: {matches}"
    )

    print(
        f"Storie individuate: {len(clusters)}"
    )

    print(
        f"Storie multi-fonte: {multi_source}"
    )

    print(
        f"Dimensione massima storia: {max_size}"
    )

    return clusters


# ============================================================
# SELEZIONE EDITORIALE
# ============================================================

def select_editorial_stories(clusters):

    print()
    print("SELEZIONE EDITORIALE")
    print("-" * 46)

    # Prima ordiniamo per qualità editoriale.
    clusters = sorted(
        clusters,
        key=lambda x: (
            x.get("editorial_score", 0),
            x.get("source_count", 0),
            x.get("article_count", 0),
            x.get("published") or ""
        ),
        reverse=True
    )

    selected = []

    source_count = {}

    category_count = {}

    ai_count = 0

    # --------------------------------------------------------
    # Limite massimo per categoria.
    #
    # Non vogliamo 30 storie AI e 3 di tutto il resto.
    # --------------------------------------------------------

    max_per_category = max(
        5,
        int(MAX_GEMINI_STORIES * 0.25)
    )

    for cluster in clusters:

        if len(selected) >= MAX_GEMINI_STORIES:
            break

        source = cluster.get(
            "source",
            ""
        )

        category = cluster.get(
            "category",
            "Tecnologia"
        )

        # ----------------------------------------------------
        # Limite fonte
        # ----------------------------------------------------

        if source_count.get(
            source,
            0
        ) >= MAX_ITEMS_PER_SOURCE:

            continue

        # ----------------------------------------------------
        # Limite AI
        # ----------------------------------------------------

        if category == "AI":

            if ai_count >= MAX_AI_STORIES:
                continue

        # ----------------------------------------------------
        # Limite categoria
        # ----------------------------------------------------

        if category_count.get(
            category,
            0
        ) >= max_per_category:

            continue

        selected.append(
            cluster
        )

        source_count[source] = (
            source_count.get(source, 0) + 1
        )

        category_count[category] = (
            category_count.get(category, 0) + 1
        )

        if category == "AI":
            ai_count += 1

    # --------------------------------------------------------
    # Secondo pass:
    # se abbiamo ancora spazio, riempiamo senza i limiti
    # di categoria, ma mantenendo il limite fonte.
    # --------------------------------------------------------

    if len(selected) < MAX_GEMINI_STORIES:

        selected_ids = {
            item["cluster_id"]
            for item in selected
        }

        for cluster in clusters:

            if len(selected) >= MAX_GEMINI_STORIES:
                break

            if cluster["cluster_id"] in selected_ids:
                continue

            source = cluster.get(
                "source",
                ""
            )

            if source_count.get(
                source,
                0
            ) >= MAX_ITEMS_PER_SOURCE:
                continue

            selected.append(
                cluster
            )

            selected_ids.add(
                cluster["cluster_id"]
            )

            source_count[source] = (
                source_count.get(source, 0) + 1
            )

    return selected


# ============================================================
# DISTRIBUZIONE
# ============================================================

def print_distribution(items):

    categories = {}

    sources = {}

    for item in items:

        category = item.get(
            "category",
            "Tecnologia"
        )

        source = item.get(
            "source",
            ""
        )

        categories[category] = (
            categories.get(category, 0) + 1
        )

        sources[source] = (
            sources.get(source, 0) + 1
        )

    print()
    print("DISTRIBUZIONE EDITORIALE")
    print("-" * 46)

    print()
    print("Categorie:")

    for category, count in sorted(
        categories.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        print(
            f"  {category:<28} {count}"
        )

    print()
    print("Fonti:")

    for source, count in sorted(
        sources.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        print(
            f"  {source:<28} {count}"
        )


# ============================================================
# PREPARAZIONE GEMINI
# ============================================================

def prepare_for_ai(selected):

    result = []

    for story in selected:

        result.append({

            "cluster_id": story["cluster_id"],

            "title": story["title"],

            "description": story["description"],

            "url": story["url"],

            "image": story.get("image"),

            "source": story["source"],

            "published": story.get("published"),

            "category": story["category"],

            "editorial_score": story[
                "editorial_score"
            ],

            "source_count": story[
                "source_count"
            ],

            "article_count": story[
                "article_count"
            ],

            "sources": story[
                "sources"
            ]
        })

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 46)
    print("       AI VISION - RSS COLLECTOR 2.3")
    print("=" * 46)

    # --------------------------------------------------------
    # RACCOLTA
    # --------------------------------------------------------

    items, feed_status = collect_items()

    print()
    print("=" * 46)
    print("RIEPILOGO RACCOLTA")
    print("-" * 46)

    print(
        f"Articoli raccolti: {len(items)}"
    )

    # --------------------------------------------------------
    # Ordinamento globale
    #
    # IMPORTANTE:
    # non utilizziamo più l'ordine dei feed.
    # --------------------------------------------------------

    items = sorted(
        items,
        key=lambda x: (
            x.get("published") or "",
            x.get("editorial_score", 0)
        ),
        reverse=True
    )

    # Limite globale
    items = items[:MAX_TOTAL_ITEMS]

    # --------------------------------------------------------
    # DEDUPLICA
    # --------------------------------------------------------

    items, duplicates = exact_deduplicate(
        items
    )

    print(
        f"Duplicati esatti eliminati: {duplicates}"
    )

    print(
        f"Articoli dopo deduplica: {len(items)}"
    )

    # --------------------------------------------------------
    # CLUSTERING
    # --------------------------------------------------------

    clusters = build_clusters(
        items
    )

    # --------------------------------------------------------
    # DISTRIBUZIONE COMPLETA
    # --------------------------------------------------------

    print_distribution(
        clusters
    )

    # --------------------------------------------------------
    # SELEZIONE
    # --------------------------------------------------------

    selected = select_editorial_stories(
        clusters
    )

    print()

    print(
        f"Storie selezionate: {len(selected)}"
    )

    # --------------------------------------------------------
    # PREPARAZIONE GEMINI
    # --------------------------------------------------------

    ai_items = prepare_for_ai(
        selected
    )

    print(
        f"Storie preparate per Gemini: "
        f"{len(ai_items)}"
    )

    # --------------------------------------------------------
    # DISTRIBUZIONE FINALE
    # --------------------------------------------------------

    print()
    print("DISTRIBUZIONE FINALE")
    print("-" * 46)

    final_categories = {}

    for item in ai_items:

        category = item.get(
            "category",
            "Tecnologia"
        )

        final_categories[category] = (
            final_categories.get(category, 0) + 1
        )

    for category, count in sorted(
        final_categories.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        print(
            f"  {category:<28} {count}"
        )

    # --------------------------------------------------------
    # TOP 15
    # --------------------------------------------------------

    print()
    print("TOP 15 STORIE SELEZIONATE")
    print("-" * 46)

    for index, item in enumerate(
        ai_items[:15],
        start=1
    ):

        print(
            f"{index:02d}. "
            f"[{item['category']}] "
            f"[{item['editorial_score']}] "
            f"{item['title']}"
        )

        print(
            f"    Fonte: {item['source']} | "
            f"Fonti storia: {item['source_count']}"
        )

    # --------------------------------------------------------
    # OUTPUT JSON
    # --------------------------------------------------------

    os.makedirs(
        "data",
        exist_ok=True
    )

    output = {

        "collector_version": VERSION,

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "config": {
            "max_age_hours": MAX_AGE_HOURS,
            "max_total_items": MAX_TOTAL_ITEMS,
            "max_gemini_stories": MAX_GEMINI_STORIES,
            "cluster_threshold": CLUSTER_THRESHOLD,
            "max_items_per_source": MAX_ITEMS_PER_SOURCE,
            "max_ai_stories": MAX_AI_STORIES
        },

        "stats": {

            "raw_items": len(items),

            "duplicates_removed": duplicates,

            "clusters": len(clusters),

            "multi_source_clusters": sum(
                1
                for cluster in clusters
                if cluster["source_count"] > 1
            ),

            "selected_stories": len(selected),

            "ai_stories": len(ai_items)
        },

        "feed_status": feed_status,

        # Tutte le storie individuate.
        # Utile per analisi/debug futuri.
        "clusters": clusters,

        # Questo resta il campo principale
        # da utilizzare nel passaggio successivo.
        "items": ai_items
    }

    output_path = (
        "data/rss_items.json"
    )

    with open(
        output_path,
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
    print("=" * 46)
    print("RSS COLLECTOR 2.3 COMPLETATO")
    print("=" * 46)

    print(
        f"Output: {output_path}"
    )

    print()


if __name__ == "__main__":
    main()
