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
    def test_source_reader_extracts_article_and_ignores_navigation(self):
        body = " ".join(f"contenuto{index}" for index in range(140))
        markup = (
            "<html><body><nav>menu laterale ignorato</nav>"
            "<article><h1>Titolo articolo</h1><p>" + body + "</p>"
            "<div class=\"sidebar related-articles\">notizia laterale non pertinente</div>"
            "<aside>pubblicità e altri articoli ignorati</aside></article>"
            "</body></html>"
        ).encode("utf-8")

        class FakeResponse:
            status_code = 200
            headers = {"Content-Type": "text/html"}
            encoding = "utf-8"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size):
                yield markup

        with unittest.mock.patch(
            "article_generator.requests.get", return_value=FakeResponse()
        ) as mocked_get:
            result = generator.enrich_source({
                "url": "https://www.smartworld.it/articolo",
                "description": "Breve descrizione RSS",
            })

        self.assertEqual(result["source_text_status"], "page_extracted")
        self.assertGreaterEqual(result["source_text_word_count"], 100)
        self.assertIn("contenuto139", result["source_text"])
        self.assertNotIn("menu laterale", result["source_text"])
        self.assertNotIn("pubblicità", result["source_text"])
        self.assertNotIn("notizia laterale", result["source_text"])
        mocked_get.assert_called_once()

    def test_source_reader_does_not_fetch_unapproved_domains(self):
        with unittest.mock.patch("article_generator.requests.get") as mocked_get:
            result = generator.enrich_source({
                "url": "https://example.org/article",
                "description": "Descrizione RSS sufficiente " + unique_words("dato", 150),
            })

        self.assertEqual(result["source_text_status"], "rss_fallback")
        self.assertEqual(result["source_text"], "")
        mocked_get.assert_not_called()

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

    def test_paraphrased_paragraphs_in_source_order_are_flagged(self):
        source_parts = []
        article_parts = []
        for section in range(3):
            source_words = [f"tema{section}dato{index}" for index in range(30)]
            article_words = source_words[:23] + [f"rielaborato{section}{index}" for index in range(7)]
            source_parts.append(" ".join(source_words))
            # Riordina le parole per non dipendere soltanto dalle sequenze esatte.
            article_parts.append(" ".join(reversed(article_words)))
        result = originality.assess_originality(
            "\n\n".join(article_parts),
            "\n".join(source_parts),
            source_status="page_extracted",
        )
        self.assertGreaterEqual(result["structural_similarity"], 0.80)
        self.assertIn(result["status"], {"review_required", "blocked"})
        self.assertFalse(result["publishable"])

    def test_reordered_paragraphs_reduce_structural_order_score(self):
        source_parts = []
        article_parts = []
        for section in range(3):
            words = [f"tema{section}dato{index}" for index in range(30)]
            source_parts.append(" ".join(words))
            article_parts.append(" ".join(reversed(words)))
        result = originality.assess_originality(
            "\n\n".join(reversed(article_parts)),
            "\\n".join(source_parts),
            source_status="page_extracted",
        )
        self.assertLess(result["structural_order_ratio"], 0.50)

    def test_source_reference_link_is_https_external_and_attributed(self):
        link = publisher.source_reference_link({
            "source_url": "https://example.com/news/story",
            "source": "Example News",
        }, "https://aivision.altervista.org")
        self.assertIn('href="https://example.com/news/story"', link)
        self.assertIn("Example News", link)
        self.assertEqual(publisher.source_reference_link({"source_url": "http://example.com/a"}, "https://aivision.altervista.org"), "")
        self.assertEqual(publisher.source_reference_link({"source_url": "https://aivision.altervista.org/other"}, "https://aivision.altervista.org"), "")

    def test_external_image_requires_explicit_rights_and_license(self):
        draft = {"source_image_url": "https://images.example.com/photo.jpg", "image_license": "unknown"}
        self.assertFalse(publisher.image_rights_approved(draft))
        draft.update({"image_rights_status": "permission_granted", "image_license": "Written permission"})
        self.assertTrue(publisher.image_rights_approved(draft))
        draft.update({"image_rights_status": "cc_by", "image_license": "CC BY 4.0", "image_attribution": "Photographer / source"})
        self.assertTrue(publisher.image_rights_approved(draft))
        draft["image_attribution"] = ""
        self.assertFalse(publisher.image_rights_approved(draft))

    def test_publisher_blocks_affiliate_claim_without_affiliate_links(self):
        body = unique_words("contenuto", 600) + "\\n\\nI link affiliati potrebbero generare una commissione."
        draft = {
            "generator_version": "5.0",
            "title": "Titolo articolo con contenuto editoriale",
            "body_markdown": body,
            "originality_check": {"status": "pass", "publishable": True, "reasons": []},
        }
        with self.assertRaisesRegex(publisher.PublisherError, "frase interna/di attribuzione vietata"):
            publisher.publish_one(draft, datetime.now(timezone.utc), MagicMock(), None)

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

    def test_hash_ad_marker_is_detected_before_markdown_cleanup(self):
        source = "#ad " + unique_words("fonte", 150)
        article = unique_words("redazione", 150)
        result = originality.assess_originality(
            article, source, source_status="page_extracted"
        )
        self.assertTrue(result["commercial_source_detected"])
        self.assertEqual(result["commercial_source_marker"], "#ad")
        self.assertEqual(result["status"], "review_required")

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
