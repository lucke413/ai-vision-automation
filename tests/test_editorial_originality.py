import sys
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import article_generator as generator
import editorial_originality as originality
import wp_publisher as publisher


def unique_words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{index}" for index in range(count))


class EditorialOriginalityTests(unittest.TestCase):
    def test_exact_source_copy_is_blocked(self):
        source = unique_words("parola", 180)
        result = originality.assess_originality(
            source, source, source_status="page_extracted"
        )
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["publishable"])
        self.assertEqual(result["shared_7gram_ratio"], 1.0)
        self.assertGreaterEqual(result["longest_exact_match_words"], 28)

    def test_one_copied_paragraph_is_blocked_even_with_new_surrounding_text(self):
        copied = unique_words("frase", 65)
        source = copied + "\n\n" + unique_words("sorgente", 120)
        article = copied + "\n\n" + unique_words("redazione", 140)
        result = originality.assess_originality(
            article, source, source_status="page_extracted"
        )
        self.assertEqual(result["status"], "blocked")
        self.assertGreaterEqual(result["max_paragraph_7gram_ratio"], 0.42)

    def test_independent_text_with_only_shared_product_terms_passes(self):
        source = "TCL SQD Mini LED " + unique_words("sorgente", 150)
        article = "TCL SQD Mini LED " + unique_words("analisi", 150)
        result = originality.assess_originality(
            article, source, source_status="page_extracted"
        )
        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["publishable"])

    def test_rss_fallback_without_full_source_requires_manual_review(self):
        source = unique_words("estratto", 140)
        article = unique_words("articolo", 150)
        result = originality.assess_originality(
            article, source, source_status="rss_fallback"
        )
        self.assertEqual(result["status"], "review_required")
        self.assertFalse(result["publishable"])
        self.assertTrue(any("testo integrale" in reason for reason in result["reasons"]))

    def test_missing_sponsored_disclosure_requires_manual_review(self):
        source = "In collaborazione con TCL. " + unique_words("fonte", 150)
        article = "La nuova gamma di televisori. " + unique_words("redazione", 150)
        result = originality.assess_originality(
            article, source, source_status="page_extracted"
        )
        self.assertTrue(result["commercial_source_detected"])
        self.assertFalse(result["commercial_disclosure_present"])
        self.assertEqual(result["status"], "review_required")
        self.assertFalse(result["publishable"])

    def test_preserved_sponsored_disclosure_is_not_flagged_by_itself(self):
        source = "In collaborazione con TCL. " + unique_words("fonte", 150)
        article = "Contenuto realizzato in collaborazione con TCL. " + unique_words("redazione", 150)
        result = originality.assess_originality(
            article, source, source_status="page_extracted"
        )
        self.assertTrue(result["commercial_source_detected"])
        self.assertTrue(result["commercial_disclosure_present"])
        self.assertEqual(result["status"], "pass")

    def test_practical_guides_use_their_own_editorial_brief(self):
        result = originality.assess_originality(
            unique_words("guida", 120),
            "",
            source_status="rss_fallback",
            editorial_kind="GUIDA",
        )
        self.assertEqual(result["status"], "not_applicable")
        self.assertTrue(result["publishable"])

    def test_generator_distinctiveness_rejects_unchecked_new_drafts(self):
        draft = {
            "generator_version": "4.9",
            "title": "Titolo sufficientemente informativo per un articolo",
            "body_markdown": unique_words("corpo", 120),
        }
        self.assertEqual(
            generator.editorial_distinctiveness(draft, []),
            "controllo originalità mancante",
        )

    def test_generator_distinctiveness_rejects_review_required_drafts(self):
        draft = {
            "generator_version": "4.9",
            "title": "Titolo sufficientemente informativo per un articolo",
            "body_markdown": unique_words("corpo", 120),
            "originality_check": {
                "status": "review_required",
                "publishable": False,
                "reasons": ["fonte integrale non disponibile"],
            },
        }
        reason = generator.editorial_distinctiveness(draft, [])
        self.assertIn("originalità non superata", reason)
        self.assertIn("fonte integrale", reason)

    def test_publisher_blocks_new_generator_draft_without_check(self):
        draft = {
            "generator_version": "4.9",
            "title": "Titolo articolo con contenuto editoriale",
            "body_markdown": unique_words("corpo", 600),
        }
        with self.assertRaisesRegex(publisher.PublisherError, "controllo mancante"):
            publisher.publish_one(
                draft, datetime.now(timezone.utc), MagicMock(), None
            )

    def test_publisher_blocks_new_generator_draft_with_failed_check(self):
        draft = {
            "generator_version": "4.9",
            "title": "Titolo articolo con contenuto editoriale",
            "body_markdown": unique_words("corpo", 600),
            "originality_check": {
                "status": "blocked",
                "publishable": False,
                "reasons": ["sequenza copiata"],
            },
        }
        with self.assertRaisesRegex(publisher.PublisherError, "Originality gate"):
            publisher.publish_one(
                draft, datetime.now(timezone.utc), MagicMock(), None
            )


if __name__ == "__main__":
    unittest.main()
