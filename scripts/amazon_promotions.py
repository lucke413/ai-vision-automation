#!/usr/bin/env python3
"""Verify and publish AI Vision's Amazon Italia offers in the daily workflow."""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import requests
from PIL import Image, ImageDraw, ImageFont

if __package__:
    from .amazon_affiliate import DISCLOSURE, MARKER, SITE_HOSTS, configured_tag, product_asin, tracking_tag
    from article_generator import SourceArticleParser
    from .wp_publisher import WordPressClient, env_bool, get_timezone, publish_one, save_json, slugify
else:
    from amazon_affiliate import DISCLOSURE, MARKER, SITE_HOSTS, configured_tag, product_asin, tracking_tag
    from article_generator import SourceArticleParser
    from wp_publisher import WordPressClient, env_bool, get_timezone, publish_one, save_json, slugify

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config/amazon-promotions.json"
REPORT = ROOT / "data/amazon_promotions_report.json"
AMAZON = "https://www.amazon.it"
NEWS_HOST = "www.aboutamazon.it"
MARK = "aivision-amazon-promo"
ONGOING = "Selezione Amazon AI Vision"
MONTHS = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
MONTH_PATTERN = "|".join(MONTHS)
DATE_PATTERN = rf"\b([0-3]?\d)(?:°)?\s+({MONTH_PATTERN})(?:\s+(20\d{{2}}))?\b"
BLOCK = re.compile(r"<!-- aivision-amazon-promo ([^ <>]+) -->.*?<!-- /aivision-amazon-promo -->", re.S)
ARCHIVE = "<p>Questa offerta è terminata. Prezzo e disponibilità possono essere diversi da quelli della pubblicazione.</p>"
SAFETY_WINDOW = timedelta(minutes=75)

CAMPAIGNS = (
    ("Black Friday", r"black-friday|cyber-monday", "/blackfriday"),
    ("Festa delle Offerte Prime", r"festa-(?:delle-)?offerte-prime", "/primebigdealdays"),
    ("Prime Day", r"prime-day", "/primeday"),
    ("Festa delle Offerte di Primavera", r"festa-delle-offerte-di-primavera", "/springdealdays"),
    ("Settimana della Tecnologia", r"settimana-(?:della-)?tecnologia|offerte-di-tecnologia", "/deals"),
)

@dataclass(frozen=True)
class Category:
    title: str
    query: str
    product: str
    why: str
    caveat: str
    scene: str


CATEGORIES = (
    Category("Audio", "cuffie bluetooth", r"cuffi|auricolar",
             "Ha senso se vuoi ascoltare in mobilità senza un cavo tra telefono e cuffie.",
             "Verifica comodità, autonomia e codec del tuo dispositivo.",
             "wireless headphones"),
    Category("PC e archiviazione", "ssd", r"\bssd\b",
             "È una possibilità per espandere lo spazio o sostituire un'unità lenta.",
             "Controlla formato, interfaccia e spazio libero nel tuo computer.",
             "compact solid-state drive"),
    Category("Casa smart", "presa smart wifi", r"\bpres[ae]\b",
             "È pensata per programmare l'accensione di piccoli elettrodomestici compatibili.",
             "Controlla carico massimo, tipo di presa e compatibilità con la rete di casa.",
             "smart plug and warm lamp"),
    Category("Gaming", "controller gaming", r"\bcontroller\b|\bgamepad\b",
             "Può servire come secondo pad o per sostituire un controller usurato.",
             "Verifica piattaforma supportata, tipo di connessione e alimentazione.",
             "game controller"),
    Category("Accessori smartphone", "power bank", r"power\s*bank|batteria portatile",
             "È una scelta pratica se il telefono arriva scarico a metà giornata.",
             "Prima di comprarlo, verifica capacità, peso e potenza USB-C.",
             "USB-C power bank"),
)


@dataclass(frozen=True)
class Offer:
    key: str
    category: str
    title: str
    description: str
    why: str
    terms: str
    url: str
    expires: datetime
    price: str = ""
    savings: int = 0
    affiliate: bool = False
    starts: datetime | None = None
    evidence_url: str = ""


def italian_date(day: date, year: bool = True) -> str:
    value = f"{day.day} {MONTHS[day.month - 1]}"
    return f"{value} {day.year}" if year else value


def local_at(day: date, hour: int = 0, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), get_timezone())


def parsed_date(match: re.Match, year: int) -> date:
    return date(int(match[3] or year), MONTHS.index(match[2]) + 1, int(match[1]))


def valid_https(url: str, hosts: set[str]) -> bool:
    try:
        parts = urlsplit(url)
        return parts.scheme == "https" and parts.netloc in hosts
    except ValueError:
        return False


def affiliate_url(url: str, tag: str) -> str:
    parts = urlsplit(url)
    params = parse_qs(parts.query, keep_blank_values=True)
    params["tag"] = [tag]
    return urlunsplit(parts._replace(query=urlencode(params, doseq=True)))


def public_html(session: requests.Session, url: str) -> str:
    if not valid_https(url, {NEWS_HOST}):
        return ""
    try:
        response = session.get(url, timeout=(5, 10), allow_redirects=False)
        if response.status_code == 200 and "text/html" in response.headers.get("Content-Type", ""):
            return response.text
    except requests.RequestException:
        pass
    return ""


def dated_campaign(line: str, day: date) -> tuple[datetime, datetime] | None:
    months = MONTH_PATTERN
    normalized = re.sub(r"\b(?:lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica) ", "", line.lower())
    dates = list(re.finditer(DATE_PATTERN, normalized))
    try:
        if len(dates) == 2 and re.search(r"\b(?:al?|fino|termin|durer|e)\b", normalized[dates[0].end():dates[1].start()]):
            start, end = (parsed_date(m, day.year) for m in dates)
        else:
            pair = re.search(rf"\b(\d{{1,2}})(?:°)?\s+(?:al|e)\s+(\d{{1,2}})\s+({months})(?:\s+(20\d{{2}}))?", normalized)
            if not pair:
                return None
            month, year = MONTHS.index(pair[3]) + 1, int(pair[4] or day.year)
            start, end = date(year, month, int(pair[1])), date(year, month, int(pair[2]))
    except ValueError:
        return None
    if not 0 <= (end - start).days <= 16:
        return None
    start_time = local_at(start, 0, 1) if "00:01" in normalized else local_at(start)
    return start_time, local_at(end + timedelta(days=1))


def newsroom_offers(session: requests.Session, now: datetime, tag: str, overrides: dict,
                    evidence_urls: list[str] | None = None) -> list[Offer]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    urls = dict.fromkeys(config["announcements"] if evidence_urls is None else evidence_urls)
    campaigns = {}
    services = {}
    for index in config["newsroom"] if evidence_urls is None else []:
        page = public_html(session, index)
        for path in re.findall(r'href="(/notizie/[^"?#]+)"', page):
            if re.search(r"black-friday|prime-day|offerte-(?:prime|di-primavera)|settimana-.*tecnologia|"
                         r"offerte-di-tecnologia|lettura|audible|kindle|music-unlimited|prime-video", path):
                urls[urljoin(index, path)] = None
    for url in list(urls)[:16]:
        page = public_html(session, url)
        stamp = re.search(r'<meta property="article:published_time" content="(\d{4}-\d{2}-\d{2})', page)
        if not stamp:
            continue
        announced = date.fromisoformat(stamp[1])
        if not 0 <= (now.date() - announced).days <= 100:
            continue
        parser = SourceArticleParser()
        parser.feed(page)
        lines = parser.text().splitlines()
        for title, rule, path in CAMPAIGNS:
            if not re.search(rule, url):
                continue
            for line in sorted(lines, key=lambda value: "00:01" not in value):
                if title.casefold() not in line.casefold() or "offert" not in line.casefold():
                    continue
                period = dated_campaign(line, announced)
                if not period:
                    continue
                start, end = period
                if start - timedelta(days=1) <= now < end:
                    key = f"{slugify(title)}-{start.date().isoformat()}"
                    offer = Offer(key, "Eventi Amazon", title,
                                  "L'evento riunisce offerte in più categorie. La disponibilità dei singoli prodotti può variare durante la giornata.",
                                  "Conviene partire dai modelli che avevi già scelto e controllare versione, venditore e costo totale.",
                                  "", affiliate_url(AMAZON + path, tag), end, affiliate=True, starts=start, evidence_url=url)
                    campaigns.setdefault(key, offer)
                    break
        for line in lines:
            for offer in service_offers(line, announced, now, tag, overrides):
                services.setdefault(offer.key, replace(offer, evidence_url=url))
            if "mese della lettura" in url.replace("-", " ") and "eBook Kindle a partire" in line:
                match = re.search(r"fino al " + DATE_PATTERN, line, re.I)
                if match:
                    deadline = local_at(parsed_date(match, announced.year) + timedelta(days=1))
                    if now < deadline:
                        services.setdefault("ebook-kindle", Offer(
                            "ebook-kindle", "Lettura digitale", "eBook Kindle",
                            "La selezione del Mese della Lettura raccoglie titoli in formato digitale, da leggere sul Kindle o nell'app.",
                            "Può convenire se hai già un titolo in lista. Inizia dall'anteprima per verificare edizione e lingua.",
                            f"Campagna fino al {italian_date(deadline.date() - timedelta(days=1))}.",
                            affiliate_url(AMAZON + "/amz-books/book-deals", tag), deadline, affiliate=True, evidence_url=url))
    return [*campaigns.values(), *services.values()]


SERVICES = {
    "audible": ("Audible Premium", "Audiolibri", "Utile se ascolti durante i viaggi o preferisci una voce narrante alla lettura su schermo.",
                "https://www.audible.it/ep/holiday-offer"),
    "kindle": ("Kindle+", "Lettura digitale", "Ha senso se leggi con regolarità e trovi nel catalogo libri che avresti comunque comprato.", ""),
    "music": ("Amazon Music Unlimited", "Musica", "Utile se ascolti interi album o playlist regolarmente e vuoi confrontare catalogo e compatibilità con i tuoi dispositivi.", ""),
    "prime-video": ("Prime Video", "Streaming", "Ha senso se nel catalogo del canale ci sono già serie o film che vuoi vedere durante i mesi promozionali.", ""),
}


def service_offers(line: str, announced: date, now: datetime, tag: str, overrides: dict):
    text = line.casefold()
    for key, (title, category, why, default_url) in SERVICES.items():
        if title.casefold() not in text:
            continue
        if not any(term in text for term in ("clienti idonei", "nuovi clienti", "mai stati iscritti")):
            continue
        terms = re.search(r"(?:offerta è valida|valida|adesione|iscriverti)?\s*fino al " + DATE_PATTERN, text)
        price = re.search(r"\b(?:a\s+(?:soli\s+)?)(\d{1,3},\d{2})\s*€(\s+al mese)?", text)
        renewal = re.search(r"rinnova?[^€]{0,120}?(\d{1,3},\d{2})\s*€", text)
        duration = re.search(r"\b(uno|un|due|tre|quattro|sei|[1-9])\s+(mes[ei])\b", text)
        if not all((terms, price, renewal, duration)):
            continue
        try:
            deadline = local_at(parsed_date(terms, announced.year) + timedelta(days=1))
        except ValueError:
            continue
        if not now < deadline <= local_at(announced + timedelta(days=100)):
            continue
        # The same paragraph must name just one subscription with a price.
        if sum(text.count(item[0].casefold()) for item in SERVICES.values()) > 1:
            continue
        url = str(overrides.get(key, ""))
        affiliated = False
        if valid_https(url, SITE_HOSTS):
            if tracking_tag(url) not in {"", tag}:
                continue
            url = affiliate_url(url, tag)
            affiliated = True
        elif valid_https(url, {"amzn.to", "www.audible.it", "www.primevideo.com"}):
            # These destinations can use campaign-specific links supplied by the owner.
            affiliated = True
        else:
            url = default_url if key == "audible" and deadline.date() == date(2026, 12, 29) else ""
        if not url:
            continue
        cost = price[1] + " €" + (" al mese" if price[2] else " per il periodo")
        yield Offer(
            f"{key}-{deadline.date().isoformat()}", category, title,
            f"Abbonamento in promozione per {duration[1]} {duration[2]}, riservato ai clienti idonei.",
            why, f"Adesioni fino al {italian_date(deadline.date() - timedelta(days=1))}. "
            f"Rinnovo automatico a {renewal[1]} € al mese alla fine del periodo promozionale.",
            url, deadline, cost, affiliate=affiliated,
        )


def parse_utc(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        raise ValueError("Manca il fuso orario nella data dell'offerta.")
    return timestamp


class CreatorsAPI:
    RESOURCES = (
        "itemInfo.title", "offersV2.listings.price", "offersV2.listings.availability",
        "offersV2.listings.condition", "offersV2.listings.dealDetails",
        "offersV2.listings.isBuyBoxWinner", "parentASIN",
    )
    MARKETPLACE = "www.amazon.it"

    def __init__(self, session: requests.Session, tag: str):
        self.session, self.tag = session, tag
        self.token = ""

    def items(self, operation: str, **fields) -> list[dict]:
        if not self.token:
            response = self.session.post(
                "https://api.amazon.co.uk/auth/o2/token", timeout=15, allow_redirects=False, json={
                    "grant_type": "client_credentials", "client_id": os.environ["AMAZON_CREATORS_CREDENTIAL_ID"],
                    "client_secret": os.environ["AMAZON_CREATORS_CREDENTIAL_SECRET"], "scope": "creatorsapi::default",
                })
            response.raise_for_status()
            self.token = response.json()["access_token"]
        response = self.session.post(
            "https://creatorsapi.amazon/catalog/v1/" + operation, timeout=15, allow_redirects=False,
            headers={"Authorization": f"Bearer {self.token}", "x-marketplace": self.MARKETPLACE},
            json={"marketplace": self.MARKETPLACE, "partnerTag": self.tag, "resources": self.RESOURCES, **fields},
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("searchResult" if operation == "searchItems" else "itemsResult") or {}
        return result.get("items") or []

    def shortlist(self, now: datetime) -> list[tuple[Category, Offer]]:
        selected = []
        used = set()
        for category in CATEGORIES:
            items = self.items("searchItems", keywords=category.query, itemCount=10,
                               condition="New", minSavingPercent=5)
            offers = []
            for item in items:
                offer = product_offer(item, category, now, self.tag)
                if offer:
                    offers.append((item.get("parentASIN") or offer.key, offer))
            for family, offer in sorted(offers, key=lambda pair: pair[1].savings, reverse=True):
                if family in used or sum(c == category for c, _ in selected) >= 2:
                    continue
                selected.append((category, offer))
                used.add(family)
        return selected

    def verify(self, selections: list[tuple[Category, Offer]], now: datetime) -> list[Offer]:
        if not selections:
            return []
        selected = {offer.key: category for category, offer in selections}
        items = self.items("getItems", itemIds=list(selected), itemIdType="ASIN")
        return [
            offer for item in items
            if (category := selected.get(item.get("asin"))) and (offer := product_offer(item, category, now, self.tag))
        ]


def product_offer(item: dict, category: Category, now: datetime, tag: str) -> Offer | None:
    asin = str(item.get("asin") or "")
    url = str(item.get("detailPageURL") or "")
    if not asin or product_asin(url) != asin or tracking_tag(url) != tag:
        return None
    title = ((item.get("itemInfo") or {}).get("title") or {}).get("displayValue", "")
    if not title or not re.search(category.product, title, re.I):
        return None
    for listing in (item.get("offersV2") or {}).get("listings") or []:
        deal = listing.get("dealDetails")
        access = (deal or {}).get("accessType")
        stock = (listing.get("availability") or {}).get("type", "").replace("_", "")
        condition = (listing.get("condition") or {}).get("value", "")
        if not listing.get("isBuyBoxWinner") or listing.get("violatesMAP") is True:
            continue
        if not deal or access not in {"ALL", "PRIME_EXCLUSIVE"} or stock != "INSTOCK" or condition != "New":
            continue
        price = listing.get("price") or {}
        money = price.get("money") or {}
        try:
            savings = int((price.get("savings") or {}).get("percentage") or 0)
            amount = float(money.get("amount") or 0)
            starts = parse_utc(deal["startTime"]) if deal.get("startTime") else now
            end = parse_utc(deal["endTime"]) if deal.get("endTime") else now + timedelta(hours=4)
            if (money.get("currency") != "EUR" or not 0 < amount < 100000 or not 5 <= savings <= 100
                    or starts > now or end <= now + SAFETY_WINDOW or float(deal.get("percentClaimed") or 0) >= 100):
                continue
        except (TypeError, ValueError):
            continue
        display = f"{amount:,.2f}".translate(str.maketrans(",.", ".,")) + " €"
        terms = "Offerta riservata ai clienti Prime." if access == "PRIME_EXCLUSIVE" else ""
        return Offer(asin, category.title, " ".join(title.split())[:180], category.caveat, category.why,
                     terms, url, min(now + timedelta(hours=3), end - SAFETY_WINDOW), display, savings,
                     affiliate=True)
    return None


def render_offers(offers: list[Offer], now: datetime) -> str:
    offers = [offer for offer in offers if now < offer.expires]
    if not offers:
        return ""
    sections = [f'<div class="{MARKER}"><p>{DISCLOSURE}</p><h2>Scelte da AI Vision per voi</h2>']
    verified = now.strftime("%d/%m/%Y alle %H:%M")
    for category in dict.fromkeys(offer.category for offer in offers):
        sections.append(f"<h3>{html.escape(category)}</h3>")
        for offer in (item for item in offers if item.category == category):
            title = html.escape(offer.title)
            label = "Clicca qui per acquistarlo su Amazon" if offer.savings else "Vai alla promozione"
            rel = ' rel="sponsored nofollow"' if offer.affiliate else ""
            sections.append(f"<!-- {MARK} {offer.expires.astimezone(timezone.utc).isoformat()} -->")
            sections.append(f"<h4>{title}</h4>")
            if offer.starts:
                start = offer.starts
                until = offer.expires.date() - timedelta(days=1)
                wording = "Inizia" if start > now else "La campagna si svolge"
                sections.append(f"<p>{wording} il {italian_date(start.date())}. "
                                f"Termine il {italian_date(until)}.</p>")
            sections.append(f"<p>{html.escape(offer.description)}</p>")
            sections.append(f"<p><strong>Perché sceglierlo.</strong> {html.escape(offer.why)}</p>")
            if offer.price:
                sections.append(f"<p><strong>{html.escape(offer.price)}</strong>. "
                                f"Prezzo verificato e valido al momento della pubblicazione ({verified}, ora italiana). "
                                "Prezzi e disponibilità possono cambiare. Si applicano quelli mostrati al momento dell'acquisto.</p>")
            if offer.terms:
                sections.append(f"<p>{html.escape(offer.terms)}</p>")
            sections.append(f'<p><a href="{html.escape(offer.url, quote=True)}"{rel}>{label}</a></p>')
            sections.append(f"<!-- /{MARK} -->")
    return "\n".join([*sections, "</div>"])


def cover_label(content: bytes, label: str) -> bytes:
    using = Image.open(io.BytesIO(content)).convert("RGB")
    width, height = using.size
    canvas = ImageDraw.Draw(using)
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", width // 19)
    if canvas.textlength(label, font=font) > width * .80:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", width // 27)
    canvas.text((width * .10, height * .75), label, font=font, anchor="lm",
                fill="#fff4d7", stroke_width=4, stroke_fill="#191410")
    caption_font = ImageFont.truetype("DejaVuSans-Bold.ttf", width // 42)
    canvas.text((width * .10, height * .84), "Scelte da AI Vision per voi", font=caption_font,
                anchor="lm", fill="#fff4d7", stroke_width=2, stroke_fill="#191410")
    buffer = io.BytesIO()
    using.save(buffer, "JPEG", quality=90, optimize=True)
    return buffer.getvalue()


def expire_in_body(body: str, now: datetime) -> str:
    def hide(match):
        try:
            return ARCHIVE if parse_utc(match[1]) <= now else match[0]
        except ValueError:
            return match[0]
    return BLOCK.sub(hide, body)


def expire_posts(client: WordPressClient, now: datetime) -> int:
    if client.dry_run:
        return 0
    params = {"context": "edit", "status": "publish", "search": MARK, "per_page": 50,
              "_fields": "id,content"}
    pending = []
    for page in range(1, 100):
        response = client.session.get(client._url("posts"), params={**params, "page": page}, timeout=20)
        response.raise_for_status()
        pending.extend(response.json())
        if page >= int(response.headers.get("X-WP-TotalPages", "1")):
            break
    updated = 0
    for post in pending:
        raw = post["content"]["raw"]
        content = expire_in_body(raw, now)
        if raw == content:
            continue
        response = client.session.post(client._url(f'posts/{post["id"]}'), json={"content": content}, timeout=20)
        response.raise_for_status()
        updated += 1
    return updated


def publish_edition(client, session, title, slug, intro, scene, label, check):
    draft = {"title": title, "slug": slug, "article_id": slug, "editorial_kind": "OFFERTA",
             "category": "Offerte & Prezzi", "body_markdown": intro, "excerpt": intro,
             "seo_title": title, "seo_description": intro, "focus_keyphrase": "offerte Amazon del giorno",
             "tags": ["Amazon", ONGOING], "cover_prompt": scene}
    return publish_one(draft, datetime.now(get_timezone()), client, session, live_offer_html=check,
                       offer_cover=lambda image: cover_label(image, label))


def run(client: WordPressClient, session: requests.Session, now: datetime) -> dict:
    tag = configured_tag()
    if not tag:
        raise ValueError("Tracking ID Amazon Italia mancante.")
    overrides = json.loads(os.environ.get("AMAZON_PROMOTION_LINKS_JSON") or "{}")
    if not isinstance(overrides, dict):
        raise ValueError("AMAZON_PROMOTION_LINKS_JSON deve essere un oggetto JSON.")
    events = newsroom_offers(session, now, tag, overrides)
    services = [offer for offer in events if not offer.starts]
    campaigns = [offer for offer in events if offer.starts]
    active = next((offer for offer in campaigns if offer.starts <= now), None)
    catalog = CreatorsAPI(session, tag)
    catalog_ready = all(os.environ.get(k) for k in ("AMAZON_CREATORS_CREDENTIAL_ID", "AMAZON_CREATORS_CREDENTIAL_SECRET"))
    report = {"catalog": "credentials_missing" if not catalog_ready else "available", "items": [], "warnings": []}
    selections = []
    if not catalog_ready:
        report["warnings"].append("Credenziali Creators API mancanti: selezione da promozioni pubbliche confermate.")
    if catalog_ready:
        try:
            selections = catalog.shortlist(now)
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            report["catalog"] = "unavailable"
            report["warnings"].append(f"Ricerca Creators API: {type(exc).__name__}")

    def publish(title, slug, intro, scene, label, bundles=(), first=()):
        def recheck():
            refreshed_at = datetime.now(get_timezone())
            if refreshed_at.date() != now.date():
                return ""
            try:
                verified = catalog.verify(list(bundles), refreshed_at)
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                verified = []
                report["warnings"].append(f"Verifica prezzi Creators API: {type(exc).__name__}")
            keys = {offer.key for offer in first}
            sources = list(dict.fromkeys(offer.evidence_url for offer in first if offer.evidence_url))
            confirmed = [offer for offer in newsroom_offers(session, refreshed_at, tag, overrides, sources)
                         if offer.key in keys] if sources else []
            return render_offers([*confirmed, *verified], datetime.now(get_timezone()))
        try:
            result = publish_edition(client, session, title, slug, intro, scene, label, recheck)
            report["items"].append({k: result.get(k) for k in ("title", "status", "wp_status", "link", "post_id")})
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            report["warnings"].append(f"{slug}: {type(exc).__name__}: {exc}")

    stamp = italian_date(now.date())
    daily = []
    spotlight = []
    for category in CATEGORIES:
        same_category = [row for row in selections if row[0] == category]
        daily.extend(same_category[:1 if active else 2])
        if active:
            spotlight.extend(same_category[1:])
    if daily or services:
        suffix = f" · {active.title}" if active else ("" if daily else " · libri e abbonamenti")
        title = f"Offerte Amazon del giorno{suffix} | {stamp}"
        scene = ("Photorealistic editorial still life, gift parcels and price label with no text, " +
                 (", ".join(category.scene for category, _ in daily[:3]) if daily else
                  "stack of books, e-reader and wireless headphones") +
                 ", warm amber lighting, subjects in the upper-right of the photograph")
        intro = ("La selezione di oggi raccoglie le promozioni confermate e le organizza per categoria. "
                 "Per ogni proposta trovi a chi può servire e cosa controllare prima di acquistarla.")
        publish(title, "offerte-amazon-del-giorno-" + now.date().isoformat(), intro, scene,
                "OFFERTE DEL GIORNO" if not active else f"OFFERTE DEL GIORNO · {active.title.upper()}",
                daily, services)

    for campaign in campaigns:
        title = f"{campaign.title} Amazon {campaign.starts.year} | calendario e consigli per gli acquisti"
        intro = ("Segna l'inizio della campagna e prepara una lista con il modello preciso dei prodotti che ti interessano. "
                 "Confronta il prezzo per la stessa variante e valuta garanzia e resi se cambi venditore. "
                 "Per gli accessori, controlla prima la compatibilità con quello che possiedi già.")
        publish(title, "amazon-" + campaign.key, intro,
                "Photorealistic editorial shopping still life, charcoal gift box with burnt orange ribbon and "
                "a cardboard parcel, wireless headphones and a blank hanging ticket against a warm studio wall",
                campaign.title.upper(), first=[campaign])

    if active and spotlight:
        category, _ = spotlight[now.day % len(spotlight)]
        picks = [row for row in spotlight if row[0] == category]
        title = f"Offerte Amazon del giorno · {active.title} {category.title} | {stamp}"
        intro = ("Questa selezione aggiuntiva è dedicata a chi sta già valutando un acquisto in questa categoria. "
                 "Confronta le specifiche del modello e quello che ti serve prima di decidere.")
        publish(title, f"amazon-{slugify(active.title)}-{slugify(category.title)}-{now.date().isoformat()}",
                intro, f"Editorial photography of {category.scene}, amber tag and kraft parcel, clean counter",
                f"{active.title.upper()} · {category.title.upper()}", picks)

    if not any(row["status"] in {"published", "already_exists", "planned"} for row in report["items"]):
        report["warnings"].append("Nessun articolo promozionale verificato o pubblicabile oggi.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expire", action="store_true")
    args = parser.parse_args()
    dry = env_bool("WP_DRY_RUN", True)
    base, user, password = (os.environ.get(k, "") for k in ("WP_BASE_URL", "WP_USERNAME", "WP_APP_PASSWORD"))
    if not dry and not all((base, user, password)):
        raise RuntimeError("Credenziali WordPress mancanti.")
    client = WordPressClient(base, user, password, dry)
    now = datetime.now(get_timezone())
    if args.expire:
        print(f"Articoli promozionali aggiornati: {expire_posts(client, now)}")
        return
    with requests.Session() as session:
        report = run(client, session, now)
    save_json(REPORT, report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
