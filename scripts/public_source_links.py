"""Remove publication-only source links while keeping article text and credits."""
from __future__ import annotations

import html
import re
from urllib.parse import urlsplit

SOURCE_CLASS = "av-source-reference"
PARAGRAPH = re.compile(
    r"(?P<open><!--\s*wp:paragraph(?:\s+[^>]*?)?-->\s*)?"
    r"<p\b(?P<attrs>[^>]*)>(?P<body>.*?)</p\s*>"
    r"(?P<close>\s*<!--\s*/wp:paragraph\s*-->)?",
    re.I | re.S,
)
ANCHOR = re.compile(
    r'<a\b[^>]*?\bhref\s*=\s*(?P<quote>["\'])(?P<url>.*?)'
    r'(?P=quote)[^>]*>(?P<label>.*?)</a\s*>',
    re.I | re.S,
)
SOURCE_LABEL = re.compile(
    r"^(?:font[ei](?:\s+(?:di riferimento|original[ei]|ufficial[ei]|tecnic[ah]e?|giornalistich[ea]))?"
    r"|riferiment[oi]|bibliografia)\s*:",
    re.I,
)
EDITORIAL_HOSTS = frozenset({
    "tomshw.it", "smartworld.it", "multiplayer.it", "hwupgrade.it", "arstechnica.com",
    "everyeye.it", "techcrunch.com", "theverge.com", "dday.it", "bleepingcomputer.com",
    "hdblog.it", "hdmotori.it", "theregister.com", "dmove.it", "macrumors.com",
    "siliconera.com", "reuters.com", "krebsonsecurity.com", "pmi.it", "gamespot.com",
    "bloomberg.com", "ign.com", "videogameschronicle.com", "eurogamer.net",
    "9to5google.com", "wabetainfo.com",
})
PROTECTED = re.compile(
    r"<figcaption\b[^>]*>.*?</figcaption\s*>"
    r"|<div\b[^>]*\bav-amazon-affiliate\b[^>]*>.*?</div\s*>"
    r"|<h2\b[^>]*>\s*Prova lo strumento\s*</h2>\s*<p\b[^>]*>.*?</p>\s*<ul\b[^>]*>.*?</ul>",
    re.I | re.S,
)


def plain(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def link_key(url: str) -> tuple[str, str] | None:
    try:
        parts = urlsplit(html.unescape(url))
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return None
        return parts.hostname.casefold().removeprefix("www."), parts.path.rstrip("/")
    except ValueError:
        return None


def is_editorial_url(url: str) -> bool:
    key = link_key(url)
    return bool(key and any(key[0] == host or key[0].endswith("." + host) for host in EDITORIAL_HOSTS))


def marked_source_url(content: str) -> str:
    """Recover the original URL from the one-link footer written by the publisher."""
    for block in PARAGRAPH.finditer(content):
        if SOURCE_CLASS not in (block["attrs"] or ""):
            continue
        text = block["body"]
        links = list(ANCHOR.finditer(text))
        if len(links) == 1 and plain(text[:links[0].start()]).casefold() == "fonte:":
            return html.unescape(links[0]["url"])
    return ""


def clean_source_links(content: str, source_url: str = "") -> tuple[str, int]:
    """Remove source-only paragraphs and unlink editorial anchors in factual prose."""
    if not content:
        return content, 0
    count = 0
    source_key = link_key(source_url)

    def remove_paragraph(match: re.Match) -> str:
        nonlocal count
        body = match["body"]
        anchors = list(ANCHOR.finditer(body))
        if not anchors:
            return match[0]
        if not any(link_key(anchor["url"]) for anchor in anchors):
            return match[0]
        attrs = match["attrs"] or ""
        marked = SOURCE_CLASS in attrs
        label = SOURCE_LABEL.match(plain(body[:anchors[0].start()]))
        if not marked and not label:
            return match[0]
        if any((link_key(anchor["url"]) or ("", ""))[0] in {
            "amazon.it", "amzn.to", "creativecommons.org", "commons.wikimedia.org",
        } for anchor in anchors):
            return match[0]
        # Some manually edited footers include a separate editorial statement
        # after the citations, such as a note about historical prices or testing.
        tail = body[anchors[-1].end():].strip()
        note = re.match(r"^[.!?]\s+(\S.*)$", tail, re.S)
        if not marked and not note and plain(tail).strip(".;:–—-"):
            return match[0]
        count += len(anchors)
        if note:
            return f"{match['open'] or ''}<p>{note[1]}</p>{match['close'] or ''}"
        return ""

    def unlink(match: re.Match) -> str:
        nonlocal count
        url = match["url"]
        key = link_key(url)
        if not key or not (key == source_key or is_editorial_url(url)):
            return match[0]
        count += 1
        return "" if link_key(plain(match["label"])) else match["label"]

    protected = list(PROTECTED.finditer(content))
    cursor = 0
    pieces = []
    for region in [*protected, None]:
        end = region.start() if region else len(content)
        segment = content[cursor:end]
        # Apply before unwrapping anchors so a source paragraph can be removed
        # as a complete block, including Gutenberg's paragraph comments.
        segment = PARAGRAPH.sub(remove_paragraph, segment)
        pieces.append(ANCHOR.sub(unlink, segment))
        if region:
            pieces.append(region[0])
            cursor = region.end()
    return "".join(pieces).rstrip() if count else content, count
