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
from urllib.parse import parse_qs, urlencode, urlsplit

SITE_HOSTS = {"amazon.it", "www.amazon.it"}
TAG_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}-[0-9]{2}", re.IGNORECASE)
ASIN_PATH = re.compile(r"(?:^|/)(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:/|$)", re.IGNORECASE)
MARKER = "av-amazon-affiliate"
DISCLOSURE = "In qualità di Affiliato Amazon io ricevo un guadagno dagli acquisti idonei."
CONFIG = Path(__file__).resolve().parent.parent / "config" / "amazon-affiliate.json"
MAX_PRODUCTS = 3
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
    if CONFIG.is_file():
        try:
            return tracking_tag(str(json.loads(CONFIG.read_text(encoding="utf-8")).get("tracking_id") or ""))
        except (OSError, ValueError, AttributeError):
            return ""
    return ""


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


def article_products(draft: dict, source: str | None = None) -> list[str]:
    values = draft.get("amazon_products") or []
    if not isinstance(values, list):
        return []
    title = str(draft.get("title") or "")
    if PREVIEW_ONLY.search(title):
        return []
    body = str(draft.get("body_markdown") or "")
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
    return list(products.values())


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


@dataclass(frozen=True)
class AffiliateLink:
    product: str
    asin: str
    url: str

    def markup(self) -> str:
        product = html.escape(self.product)
        url = html.escape(self.url, quote=True)
        label = "Clicca qui per acquistarlo su Amazon" if self.asin else "Cerca questo modello su Amazon"
        return f'<p><strong>{product}</strong> <a href="{url}" rel="sponsored nofollow">{label}</a></p>'


def affiliate_section(draft: dict, body: str, tag: str) -> tuple[str, str, list[dict]]:
    products = article_products(draft)
    if not products:
        return "", "no_product", []
    tag = tracking_tag(tag)
    if not tag:
        return "", "tracking_id_missing", []
    if MARKER in body or has_affiliate_link(body):
        return "", "already_present", []
    if AMAZON_PRICE.search(str(draft.get("body_markdown") or "")) or AMAZON_PRICE.search(str(draft.get("title") or "")):
        return "", "amazon_price_in_article", []
    source_links = draft.get("amazon_source_links") or []
    if not isinstance(source_links, list):
        source_links = []
    links = []
    for product in products:
        asin = matched_asin(product, source_links)
        if asin:
            url = f"https://www.amazon.it/dp/{asin}?" + urlencode({"tag": tag})
        else:
            url = "https://www.amazon.it/s?" + urlencode({"k": product, "tag": tag})
        links.append(AffiliateLink(product, asin, url))
    markup = f'<div class="{MARKER}"><p><strong>Link affiliati Amazon</strong></p>'
    markup += "<p>" + DISCLOSURE + "</p>"
    markup += "".join(link.markup() for link in links) + "</div>"
    report = [{"product": link.product, "type": "product" if link.asin else "search", "asin": link.asin or None}
              for link in links]
    return markup, "inserted", report
