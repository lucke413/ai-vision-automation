"""Build disclosed Amazon Italia links for products grounded in the article."""
from __future__ import annotations

import html
import json
import os
import re
import unicodedata
from html.parser import HTMLParser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

SITE_HOSTS = {"amazon.it", "www.amazon.it"}
TAG_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}-[0-9]{2}", re.IGNORECASE)
ASIN_PATH = re.compile(r"(?:^|/)(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:/|$)", re.IGNORECASE)
MARKER = "av-amazon-affiliate"
DISCLOSURE = "In qualità di Affiliato Amazon io ricevo un guadagno dagli acquisti idonei."
CONFIG = Path(__file__).resolve().parent.parent / "config" / "amazon-affiliate.json"
MAX_PRODUCTS = 12
PLATFORM_TAG = "gz-blog-21"

# Price and stock data remain on Amazon. An article can still quote a
# manufacturer's MSRP without creating or repeating any Amazon price.
PRICE = r"(?:€\s*\d|\d[\d., ]*\s*(?:€|euro\b))"
AMAZON_PRICE = re.compile(
    rf"\b(?:amazon(?:\.it)?\b[^.!?\n]{{0,90}}{PRICE}|"
    rf"{PRICE}[^.!?\n]{{0,80}}\b(?:su|da)\s+amazon\b)",
    re.I,
)
PREVIEW_ONLY = re.compile(r"\b(?:rumor|indiscrezioni|concept|prototipo|trapelat\w*|leak)\b", re.I)
VEHICLE = re.compile(r"\b(?:scooter|utilitaria|berlina|minivan|motocicletta|suv|full hybrid)\b", re.I)
RETAIL_PRODUCT = re.compile(
    r"\b(?:mouse|tastier\w*|cuffi\w*|auricolar\w*|smartphone|tablet|notebook|"
    r"monitor|televisor\w*|smartwatch|controller|scheda grafica|processore|"
    r"ssd|aspirapolvere|lavapavimenti|sed(?:ia|ie)|stampant\w*|fotocamer\w*|"
    r"e-reader|altoparlant\w*|soundbar|proiettor\w*|console|power bank|videogioch[io]|"
    r"playstation\s*[45]|ps[45]|xbox\s+series|nintendo switch)\b", re.I,
)
GAMING_NEWS = re.compile(r"\b(?:gta|grand theft auto|videogioch[io]|playstation|ps[45]|xbox|nintendo switch)\b", re.I)
NON_PURCHASE_NEWS = re.compile(
    r"\b(?:gta plus|playstation plus|ps plus|game pass|abbonament\w*|gratis|gratuit\w*|"
    r"trucc(?:o|hi)|ban|patch|hotfix)\b", re.I,
)
PLATFORM_MENTION = re.compile(r"\b(?:pc|steam|windows|xbox|ps[45]|playstation\s*[45]|nintendo switch)\b", re.I)
ACCESSORY_SUBJECT = re.compile(r"\b(?:controller|dualsense|gamepad|cuffi\w*|accessori\w*)\b", re.I)
MODEL_CODE = re.compile(r"\b(?=[a-z\d-]*[a-z])(?=[a-z\d-]*\d)[a-z\d-]{3,}\b", re.I)
HEADLINE_WORDS = re.compile(r"\b(?:che|come|cosa|quando|quanto|gratis|con|del|della|aggiornament\w*|scadenz\w*)\b", re.I)


def tracking_tag(value: str) -> str:
    value = value.strip()
    if TAG_RE.fullmatch(value) and value.casefold() != PLATFORM_TAG:
        return value
    try:
        parts = urlsplit(value)
        tags = parse_qs(parts.query).get("tag", [])
        if parts.scheme == "https" and parts.netloc in SITE_HOSTS and len(tags) == 1 and TAG_RE.fullmatch(tags[0]) and tags[0].casefold() != PLATFORM_TAG:
            return tags[0]
    except ValueError:
        pass
    return ""


def configured_tag() -> str:
    value = os.environ.get("AMAZON_ASSOCIATE_TAG", "")
    if value:
        return tracking_tag(value)
    return tracking_tag(str(affiliate_config().get("tracking_id") or ""))


def affiliate_config() -> dict:
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def product_asin(url: str) -> str:
    """Extract a product ID only from an actual Amazon.it product URL."""
    try:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc not in SITE_HOSTS:
            return ""
        match = ASIN_PATH.search(parts.path)
        return match[1].upper() if match else ""
    except ValueError:
        return ""


def words(value: str) -> str:
    value = unicodedata.normalize("NFKC", html.unescape(value)).casefold()
    return " ".join(re.findall(r"[^\W_]+", value))


def mentions(name: str, text: str) -> bool:
    variant = r"pro|max|plus|ultra|mini|lite|edge|fe|se|ti"
    return bool(re.search(rf"(?<!\S){re.escape(name)}(?!\S| (?:{variant})\b)", words(text)))


def product_in_article(name: str, body: str, excerpt: str) -> bool:
    if mentions(name, body):
        return True
    # Copy often mentions the numbered series and its edition separately.
    # The excerpt must use the exact full name to establish the connection.
    edition = re.fullmatch(r"(.+\b\d+) (.+)", name)
    return bool(edition and mentions(name, excerpt)
                and mentions(edition[1], body) and mentions(edition[2], body))


def article_products(draft: dict, source: str | None = None) -> list[str]:
    values = draft.get("amazon_products") or []
    if not isinstance(values, list):
        values = []
    title = str(draft.get("title") or "")
    if PREVIEW_ONLY.search(title) or (VEHICLE.search(title) and not RETAIL_PRODUCT.search(title)):
        return []
    if GAMING_NEWS.search(title) and NON_PURCHASE_NEWS.search(title):
        return []
    body = str(draft.get("body_markdown") or "")
    excerpt = str(draft.get("excerpt") or "")
    products = {}
    for value in values:
        if not isinstance(value, str):
            continue
        value = " ".join(value.split())
        name = words(value)
        if not 5 <= len(value) <= 110 or not 2 <= len(name.split()) <= 12:
            continue
        if (source is None or mentions(name, source)) and (mentions(name, title) or mentions(name, body)):
            products.setdefault(name, value)
        if len(products) == MAX_PRODUCTS:
            break
    if products:
        return list(products.values())

    # A missing optional field need not erase a clearly named product.
    # Require an exact title subject and a product type in the headline/opening.
    if not RETAIL_PRODUCT.search(title + " " + body[:650]):
        return []
    subject = re.split(r"\s*:\s*|\s*[–—]\s*|,\s*|\s+(?i:lancia|presenta|arriva|debutta)\s+",
                       title, maxsplit=1)[0].strip()
    for value in (draft.get("cover_subject"), subject):
        if not isinstance(value, str):
            continue
        value = " ".join(value.split())
        name = words(value)
        if (HEADLINE_WORDS.search(value) or not 2 <= len(name.split()) <= 8
                or not (MODEL_CODE.search(value) or re.search(r"\b\d{1,4}\b", value))):
            continue
        # Allow a short brand/presentation prefix before the exact model.
        if not re.match(rf"^(?:\S+ ){{0,2}}{re.escape(name)}(?: |$)", words(subject)):
            continue
        if not mentions(name, title) or not product_in_article(name, body, excerpt):
            continue
        if source is not None and not mentions(name, source):
            continue
        return [value]
    return []


def matched_asin(product: str, links: list[dict]) -> str:
    """Use a source product page only when its link names the exact variant."""
    name = words(product)
    matches = set()
    for link in links:
        if not isinstance(link, dict):
            continue
        label = words(str(link.get("label") or ""))
        label = re.sub(r"^(?:compra|acquista|vedi|buy|see)\s+", "", label)
        label = re.sub(r"\s+(?:su|on|at) amazon(?: it)?$", "", label)
        asin = product_asin(str(link.get("url") or ""))
        if label == name and asin:
            matches.add(asin)
    return next(iter(matches)) if len(matches) == 1 else ""


def verified_game_editions(draft: dict) -> tuple[dict[str, str], set[str]]:
    """Resolve an explicitly discussed game to a verified edition for its platform."""
    title = str(draft.get("title") or "")
    body = str(draft.get("body_markdown") or "")
    if PREVIEW_ONLY.search(title) or NON_PURCHASE_NEWS.search(title):
        return {}, set()
    title_words = words(title)
    editions = {}
    generic_names = set()
    for game in affiliate_config().get("verified_games") or []:
        aliases = {words(alias) for alias in game["aliases"]}
        in_title = [alias for alias in aliases if mentions(alias, title)]
        if not in_title or not any(mentions(alias, body) for alias in aliases):
            continue
        first = min(title_words.index(alias) for alias in in_title)
        if ACCESSORY_SUBJECT.search(title_words[:first]):
            continue
        generic_names.update(aliases)
        platform_names = {words(platform) for platform in game["platform"]}
        generic_names.update(f"{alias} {platform}" for alias in aliases for platform in platform_names)
        generic_names.add(words(game["label"]))
        platform_text = title if PLATFORM_MENTION.search(title) else body
        if not any(mentions(platform, platform_text) or mentions(platform + " pro", platform_text)
                   for platform in platform_names):
            continue
        asin = product_asin(game["url"])
        if asin:
            editions[game["label"]] = asin
    return editions, generic_names


class ExistingAmazonLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and str(attrs.get("href") or "").startswith("https://"):
            self.links.append(attrs["href"])


def has_affiliate_link(body: str) -> bool:
    parser = ExistingAmazonLinks()
    parser.feed(body)
    return any(tracking_tag(url) for url in parser.links)


def ensure_article_tracking(body: str, tag: str, *, remove_unselected=False) -> str:
    """Finalize affiliate destinations after every source of article HTML has run."""
    if not tracking_tag(tag):
        raise ValueError("Tracking ID Amazon Italia mancante")
    edits = []
    tracked = False
    lines = body.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    class Anchors(HTMLParser):
        def handle_starttag(self, name, attrs):
            nonlocal tracked
            if name != "a":
                return
            url = dict(attrs).get("href") or ""
            parts = urlsplit(url)
            host = (parts.hostname or "").lower()
            if host not in SITE_HOSTS and host not in {"amzn.to", "amzn.eu", "a.co", "amzn.asia"} and not re.fullmatch(
                    r"(?:www\.)?amazon\.(?:com(?:\.[a-z]{2})?|co\.[a-z]{2}|[a-z]{2,3})", host):
                return
            markup = self.get_starttag_text()
            anchor = BeautifulSoup(markup, "html.parser").a
            if not remove_unselected and host in SITE_HOSTS and parts.scheme in {"http", "https", ""}:
                params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "tag"]
                anchor["href"] = urlunsplit(("https", "www.amazon.it", parts.path,
                                            urlencode([*params, ("tag", tag)]), parts.fragment))
                anchor["rel"] = list(dict.fromkeys([*anchor.get("rel", []), "sponsored", "nofollow"]))
                tracked = True
            else:
                del anchor["href"]
            line, column = self.getpos()
            start = offsets[line - 1] + column
            edits.append((start, start + len(markup), str(anchor).split("</a>")[0]))

    Anchors().feed(body)
    for start, end, replacement in reversed(edits):
        body = body[:start] + replacement + body[end:]
    if tracked and DISCLOSURE not in body:
        body += f"\n<p>{DISCLOSURE}</p>"
    return body


@dataclass(frozen=True)
class AffiliateLink:
    product: str
    asin: str
    url: str
    summary: str = ""
    why: str = ""

    def markup(self) -> str:
        product = html.escape(self.product)
        url = html.escape(self.url, quote=True)
        label = "Clicca qui per acquistarlo su Amazon" if self.asin else "Cerca questo modello su Amazon"
        link = f'<a href="{url}" rel="sponsored nofollow">{label}</a>'
        if self.summary and self.why:
            return (f"<h3>{product}</h3><p><strong>Mini recensione.</strong> {html.escape(self.summary)}</p>"
                    f"<p><strong>Perché comprarlo.</strong> {html.escape(self.why)}</p><p>{link}</p>")
        return f"<p><strong>{product}</strong> {link}</p>"


def product_notes(values: object, products: list[str]) -> dict[str, dict[str, str]]:
    if not isinstance(values, list):
        return {}
    names = {words(product) for product in products}
    collected = {}
    for value in values:
        if not isinstance(value, dict):
            continue
        name = words(str(value.get("product") or ""))
        if name not in names:
            continue
        fields = {key: " ".join(str(value.get(key) or "").split()) for key in ("summary", "why")}
        if all(22 <= len(line) <= 280 and not re.search(PRICE + r"|https?://|www\.", line, re.I)
               for line in fields.values()):
            collected.setdefault(name, fields)
    return collected


def affiliate_section(draft: dict, body: str, tag: str) -> tuple[str, str, list[dict]]:
    products = article_products(draft)
    if GAMING_NEWS.search(str(draft.get("title") or "")):
        verified, generic_names = verified_game_editions(draft)
        products = [*verified, *(product for product in products if words(product) not in generic_names)]
        products = products[:MAX_PRODUCTS]
    else:
        verified = {}
    if not products:
        return "", "no_product", []
    tag = tracking_tag(tag)
    if not tag:
        return "", "tracking_id_missing", []
    if has_affiliate_link(body):
        return "", "already_present", []
    if AMAZON_PRICE.search(str(draft.get("body_markdown") or "")) or AMAZON_PRICE.search(str(draft.get("title") or "")):
        return "", "amazon_price_in_article", []
    source_links = draft.get("amazon_source_links") or []
    if not isinstance(source_links, list):
        source_links = []
    notes = product_notes(draft.get("amazon_product_notes"), products)
    links = []
    for product in products:
        asin = verified.get(product) or matched_asin(product, source_links)
        if asin:
            url = f"https://www.amazon.it/dp/{asin}?" + urlencode({"tag": tag})
        else:
            url = "https://www.amazon.it/s?" + urlencode({"k": product, "tag": tag})
        links.append(AffiliateLink(product, asin, url, **notes.get(words(product), {})))
    markup = f'<div class="{MARKER}"><p><strong>Link affiliati Amazon</strong></p>'
    markup += "<p>" + DISCLOSURE + "</p>"
    markup += "".join(link.markup() for link in links) + "</div>"
    report = [{"product": link.product, "type": "product" if link.asin else "search", "asin": link.asin or None}
              for link in links]
    return markup, "inserted", report
