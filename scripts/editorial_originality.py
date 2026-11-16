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


VERSION = "1.1"
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

REVIEW_STRUCTURE_SCORE = 0.62
BLOCK_STRUCTURE_SCORE = 0.80
MIN_PARAGRAPH_WORDS = 20
MIN_PARAGRAPH_JACCARD = 0.30

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



def _paragraph_token_sets(value: str) -> list[set[str]]:
    """Estrae blocchi testuali separati, preservando l'ordine dei paragrafi."""
    raw = html.unescape(str(value or ""))
    raw = re.sub(r"<(script|style)\\b[^>]*>.*?</\\1>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"</?(?:p|div|section|article|h[1-6]|li|br)\\b[^>]*>", "\\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"(?m)^\\s{0,3}#{1,6}\\s*", "", raw)
    result = []
    for chunk in re.split(r"\\n+", raw):
        values = tokens(chunk)
        if len(values) >= MIN_PARAGRAPH_WORDS:
            result.append(set(values))
    return result


def _longest_increasing_ratio(values: list[int]) -> float:
    """Quota di blocchi che mantiene l'ordine della fonte (LIS stretta)."""
    if not values:
        return 0.0
    best = [1] * len(values)
    for i, value in enumerate(values):
        for j in range(i):
            if values[j] < value:
                best[i] = max(best[i], best[j] + 1)
    return max(best) / len(values)


def _paragraph_structure(article: str, source: str) -> tuple[float, float, float]:
    """Misura se i paragrafi dell'articolo seguono gli stessi blocchi e ordine.

    È un segnale prudenziale: non prova una copia semantica. Serve a inviare
    in revisione testi che cambiano le parole ma conservano la scaletta della fonte.
    """
    article_parts = _paragraph_token_sets(article)
    source_parts = _paragraph_token_sets(source)
    if len(article_parts) < 3 or len(source_parts) < 3:
        return 0.0, 0.0, 0.0
    matched_indices = []
    for part in article_parts:
        best_index = -1
        best_score = 0.0
        for index, candidate in enumerate(source_parts):
            union = len(part | candidate)
            score = len(part & candidate) / union if union else 0.0
            if score > best_score:
                best_index, best_score = index, score
        if best_score >= MIN_PARAGRAPH_JACCARD:
            matched_indices.append(best_index)
    coverage = len(matched_indices) / len(article_parts)
    order_ratio = _longest_increasing_ratio(matched_indices)
    return coverage, order_ratio, coverage * order_ratio


def _commercial_marker(source_text: str) -> str:
    raw_text = html.unescape(str(source_text or ""))
    text = raw_text + " " + plain_text(raw_text)
    for pattern in COMMERCIAL_SOURCE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return ""


def _has_disclosure(article_text: str) -> bool:
    raw_text = html.unescape(str(article_text or ""))
    text = raw_text + " " + plain_text(raw_text)
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
        "method": "exact_7gram_plus_sequence_plus_structure_v2",
        "article_words": len(article_tokens),
        "source_words": len(source_tokens),
        "shared_7gram_ratio": 0.0,
        "max_paragraph_7gram_ratio": 0.0,
        "longest_exact_match_words": 0,
        "sequence_similarity": 0.0,
        "structural_paragraph_coverage": 0.0,
        "structural_order_ratio": 0.0,
        "structural_similarity": 0.0,
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
    structural_coverage, structural_order, structural_score = _paragraph_structure(
        article_text, source_text
    )

    base.update({
        "shared_7gram_ratio": round(shared_ratio, 4),
        "max_paragraph_7gram_ratio": round(paragraph_ratio, 4),
        "longest_exact_match_words": longest_match,
        "sequence_similarity": round(sequence_ratio, 4),
        "structural_paragraph_coverage": round(structural_coverage, 4),
        "structural_order_ratio": round(structural_order, 4),
        "structural_similarity": round(structural_score, 4),
    })

    structural_block = (
        structural_score >= BLOCK_STRUCTURE_SCORE
        and structural_coverage >= 0.80
        and structural_order >= 0.85
    )
    structural_review = (
        structural_score >= REVIEW_STRUCTURE_SCORE
        and structural_coverage >= 0.65
        and structural_order >= 0.75
    )
    blocked = (
        shared_ratio >= BLOCK_NGRAM_COVERAGE
        or paragraph_ratio >= BLOCK_PARAGRAPH_COVERAGE
        or longest_match >= BLOCK_LONGEST_MATCH
        or sequence_ratio >= BLOCK_SEQUENCE_RATIO
        or structural_block
    )
    review = (
        shared_ratio >= REVIEW_NGRAM_COVERAGE
        or paragraph_ratio >= REVIEW_PARAGRAPH_COVERAGE
        or longest_match >= REVIEW_LONGEST_MATCH
        or sequence_ratio >= REVIEW_SEQUENCE_RATIO
        or structural_review
    )
    if shared_ratio >= REVIEW_NGRAM_COVERAGE:
        reasons.append("sovrapposizione elevata di sequenze testuali di sette parole")
    if paragraph_ratio >= REVIEW_PARAGRAPH_COVERAGE:
        reasons.append("almeno un paragrafo è troppo vicino al testo della fonte")
    if longest_match >= REVIEW_LONGEST_MATCH:
        reasons.append(f"sequenza consecutiva condivisa di {longest_match} parole")
    if sequence_ratio >= REVIEW_SEQUENCE_RATIO:
        reasons.append("ordine e sequenza lessicale troppo vicini alla fonte")
    if structural_review:
        reasons.append("i paragrafi mantengono una sequenza tematica troppo vicina alla struttura della fonte")
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
