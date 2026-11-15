#!/usr/bin/env python3
"""Controllo locale di somiglianza e trasparenza editoriale.

Non è un servizio antiplagio e non certifica l'originalità semantica. Rileva
riuso testuale, sequenze troppo vicine, paragrafi sovrapposti e disclosure
commerciali perse. Se la fonte integrale non è disponibile, il risultato è
review_required: la pipeline automatica non pubblica alla cieca.
"""
from __future__ import annotations

import difflib
import html
import re
import unicodedata


VERSION = "1.0"
MIN_SOURCE_WORDS = 100
NGRAM_SIZE = 7

REVIEW_NGRAM_COVERAGE = 0.07
BLOCK_NGRAM_COVERAGE = 0.16
REVIEW_PARAGRAPH_COVERAGE = 0.22
BLOCK_PARAGRAPH_COVERAGE = 0.42
REVIEW_LONGEST_MATCH = 16
BLOCK_LONGEST_MATCH = 28
REVIEW_SEQUENCE_RATIO = 0.34
BLOCK_SEQUENCE_RATIO = 0.48

WORD_RE = re.compile(r"[a-z0-9à-öø-ÿ]+", re.IGNORECASE)
COMMERCIAL_SOURCE_PATTERNS = (
    re.compile(r"\bin collaborazione con\b", re.IGNORECASE),
    re.compile(r"\bcontenuto sponsorizzato\b", re.IGNORECASE),
    re.compile(r"\bsponsorizzato da\b", re.IGNORECASE),
    re.compile(r"\bpubbliredazionale\b", re.IGNORECASE),
    re.compile(r"\bbrand content\b", re.IGNORECASE),
    re.compile(r"\bpaid partnership\b", re.IGNORECASE),
    re.compile(r"(?<!\w)#ad\b", re.IGNORECASE),
    re.compile(r"\bcontenuto in partnership con\b", re.IGNORECASE),
)
DISCLOSURE_PATTERNS = (
    re.compile(r"\bin collaborazione con\b", re.IGNORECASE),
    re.compile(r"\bcontenuto sponsorizzato\b", re.IGNORECASE),
    re.compile(r"\bsponsorizzato da\b", re.IGNORECASE),
    re.compile(r"\bpubbliredazionale\b", re.IGNORECASE),
    re.compile(r"\bbrand content\b", re.IGNORECASE),
    re.compile(r"\bpaid partnership\b", re.IGNORECASE),
    re.compile(r"(?<!\w)#ad\b", re.IGNORECASE),
    re.compile(r"\bcontenuto pubblicitario\b", re.IGNORECASE),
    re.compile(r"\bpubblicità\b", re.IGNORECASE),
)


def plain_text(value: object) -> str:
    """Converte HTML/Markdown in testo comparabile senza alterare le parole."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text, flags=re.I)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"[*_~>#|]", " ", text)
    text = text.replace(chr(96), " ")
    return " ".join(text.split())


def tokens(value: object) -> list[str]:
    text = unicodedata.normalize("NFKC", plain_text(value)).casefold()
    return WORD_RE.findall(text)


def _ngrams(values: list[str], size: int = NGRAM_SIZE) -> list[tuple[str, ...]]:
    if len(values) < size:
        return []
    return [tuple(values[i:i + size]) for i in range(len(values) - size + 1)]


def _max_paragraph_overlap(article: str, source_ngrams: set[tuple[str, ...]]) -> float:
    ratios = []
    for paragraph in re.split(r"\n\s*\n", str(article or "")):
        paragraph_tokens = tokens(paragraph)
        if len(paragraph_tokens) < 40:
            continue
        shingles = _ngrams(paragraph_tokens)
        if shingles:
            ratios.append(sum(shingle in source_ngrams for shingle in shingles) / len(shingles))
    return max(ratios, default=0.0)


def _commercial_marker(source_text: str) -> str:
    text = plain_text(source_text)
    for pattern in COMMERCIAL_SOURCE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return ""


def _has_disclosure(article_text: str) -> bool:
    text = plain_text(article_text)
    return any(pattern.search(text) for pattern in DISCLOSURE_PATTERNS)


def assess_originality(
    article_text: str,
    source_text: str,
    *,
    source_status: str | None = None,
    editorial_kind: str | None = None,
) -> dict:
    """Valuta somiglianza testuale e disclosure; non sostituisce il fact-check."""
    if str(editorial_kind or "").upper() in {"GUIDA", "TUTORIAL"}:
        return {
            "version": VERSION,
            "status": "not_applicable",
            "publishable": True,
            "method": "editorial_brief_exempt",
            "reasons": [],
            "article_words": len(tokens(article_text)),
            "source_words": len(tokens(source_text)),
            "shared_7gram_ratio": 0.0,
            "max_paragraph_7gram_ratio": 0.0,
            "longest_exact_match_words": 0,
            "sequence_similarity": 0.0,
            "commercial_source_detected": False,
            "commercial_source_marker": "",
            "commercial_disclosure_present": False,
        }

    article_tokens = tokens(article_text)
    source_tokens = tokens(source_text)
    marker = _commercial_marker(source_text)
    disclosure = _has_disclosure(article_text)
    base = {
        "version": VERSION,
        "method": "exact_7gram_plus_sequence_v1",
        "article_words": len(article_tokens),
        "source_words": len(source_tokens),
        "shared_7gram_ratio": 0.0,
        "max_paragraph_7gram_ratio": 0.0,
        "longest_exact_match_words": 0,
        "sequence_similarity": 0.0,
        "commercial_source_detected": bool(marker),
        "commercial_source_marker": marker,
        "commercial_disclosure_present": disclosure,
    }
    reasons: list[str] = []

    effective_status = source_status or ("page_extracted" if source_tokens else "rss_fallback")
    if effective_status != "page_extracted" or len(source_tokens) < MIN_SOURCE_WORDS:
        reasons.append(
            "testo integrale della fonte non disponibile o troppo breve: originalità non verificabile automaticamente"
        )
        if marker and not disclosure:
            reasons.append("la fonte segnala una collaborazione commerciale non dichiarata nell'articolo")
        return {
            **base,
            "status": "review_required",
            "publishable": False,
            "reasons": reasons,
        }

    if len(article_tokens) < 100:
        reasons.append("articolo troppo breve per un confronto affidabile")
        return {
            **base,
            "status": "review_required",
            "publishable": False,
            "reasons": reasons,
        }

    article_shingles = _ngrams(article_tokens)
    source_shingles = set(_ngrams(source_tokens))
    shared_ratio = (
        sum(shingle in source_shingles for shingle in article_shingles) / len(article_shingles)
        if article_shingles else 0.0
    )
    paragraph_ratio = _max_paragraph_overlap(article_text, source_shingles)
    matcher = difflib.SequenceMatcher(None, source_tokens, article_tokens, autojunk=True)
    longest_match = matcher.find_longest_match(
        0, len(source_tokens), 0, len(article_tokens)
    ).size
    sequence_ratio = matcher.ratio()

    base.update({
        "shared_7gram_ratio": round(shared_ratio, 4),
        "max_paragraph_7gram_ratio": round(paragraph_ratio, 4),
        "longest_exact_match_words": longest_match,
        "sequence_similarity": round(sequence_ratio, 4),
    })

    blocked = (
        shared_ratio >= BLOCK_NGRAM_COVERAGE
        or paragraph_ratio >= BLOCK_PARAGRAPH_COVERAGE
        or longest_match >= BLOCK_LONGEST_MATCH
        or sequence_ratio >= BLOCK_SEQUENCE_RATIO
    )
    review = (
        shared_ratio >= REVIEW_NGRAM_COVERAGE
        or paragraph_ratio >= REVIEW_PARAGRAPH_COVERAGE
        or longest_match >= REVIEW_LONGEST_MATCH
        or sequence_ratio >= REVIEW_SEQUENCE_RATIO
    )
    if shared_ratio >= REVIEW_NGRAM_COVERAGE:
        reasons.append("sovrapposizione elevata di sequenze testuali di sette parole")
    if paragraph_ratio >= REVIEW_PARAGRAPH_COVERAGE:
        reasons.append("almeno un paragrafo è troppo vicino al testo della fonte")
    if longest_match >= REVIEW_LONGEST_MATCH:
        reasons.append(f"sequenza consecutiva condivisa di {longest_match} parole")
    if sequence_ratio >= REVIEW_SEQUENCE_RATIO:
        reasons.append("ordine e sequenza lessicale troppo vicini alla fonte")
    if marker and not disclosure:
        reasons.append("la fonte segnala una collaborazione commerciale non dichiarata nell'articolo")

    if blocked:
        status = "blocked"
    elif review or (marker and not disclosure):
        status = "review_required"
    else:
        status = "pass"

    return {
        **base,
        "status": status,
        "publishable": status == "pass",
        "reasons": reasons,
    }
