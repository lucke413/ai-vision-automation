import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import wp_public_cleanup as cleanup


class PublicSourceCleanupTests(unittest.TestCase):
    def test_removes_only_final_linked_source_paragraph(self):
        body = (
            "<p>Tom's Hardware ha descritto il prodotto e le sue caratteristiche.</p>"
            '<p>Fonte di riferimento: <a href="https://example.com/review">Tom\'s Hardware Italia</a></p>'
        )
        cleaned, removed = cleanup.remove_last_source_footer(body)
        self.assertIn("Tom's Hardware ha descritto", cleaned)
        self.assertNotIn("Fonte di riferimento", cleaned)
        self.assertIn("<a href=", removed)

    def test_removes_gutenberg_wrapped_final_source_paragraph(self):
        body = (
            "<!-- wp:paragraph -->\n"
            "<p>Testo editoriale utile.</p>\n"
            "<!-- /wp:paragraph -->\n"
            "<!-- wp:paragraph -->\n"
            '<p>Fonte: <a href="https://example.com">Sito ufficiale</a></p>\n'
            "<!-- /wp:paragraph -->"
        )
        cleaned, removed = cleanup.remove_last_source_footer(body)
        self.assertIn("Testo editoriale utile", cleaned)
        self.assertNotIn("Sito ufficiale", cleaned)
        self.assertIn("Sito ufficiale", removed)

    def test_keeps_inline_source_attribution(self):
        body = "<p>Secondo Tom's Hardware, il dispositivo offre una nuova funzione.</p>"
        self.assertEqual(cleanup.remove_last_source_footer(body), (body, ""))

    def test_keeps_nonfinal_source_paragraph(self):
        body = (
            '<p>Fonte: <a href="https://example.com">Sito ufficiale</a></p>'
            "<p>Il testo prosegue con una spiegazione editoriale.</p>"
        )
        self.assertEqual(cleanup.remove_last_source_footer(body), (body, ""))

    def test_keeps_unlinked_source_label(self):
        body = "<p>Fonte di riferimento: Tom's Hardware Italia</p>"
        self.assertEqual(cleanup.remove_last_source_footer(body), (body, ""))

    def test_keeps_final_paragraph_with_additional_commentary(self):
        body = (
            '<p>Fonte: <a href="https://example.com">Sito ufficiale</a>. '
            "La redazione ha verificato anche altri aspetti del prodotto.</p>"
        )
        self.assertEqual(cleanup.remove_last_source_footer(body), (body, ""))

    def test_empty_content(self):
        self.assertEqual(cleanup.remove_last_source_footer(""), ("", ""))


if __name__ == "__main__":
    unittest.main()
