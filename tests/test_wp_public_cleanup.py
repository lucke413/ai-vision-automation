import unittest

from scripts.public_source_links import clean_source_links, marked_source_url


class PublicSourceCleanupTests(unittest.TestCase):
    def test_removes_generated_source_footer_and_keeps_internal_links(self):
        footer = ('<p class="av-source-reference">Fonte: '
                  '<a href="https://www.tomshw.it/review">Tom’s Hardware Italia</a>.</p>')
        body = ("<p>Tom's Hardware ha descritto il prodotto e le sue caratteristiche.</p>"
                '<p><a href="https://aivision.altervista.org/guide/">Guide</a></p>')
        self.assertEqual(marked_source_url(body + footer), "https://www.tomshw.it/review")
        self.assertEqual(clean_source_links(body + footer), (body, 1))

    def test_removes_gutenberg_source_paragraph_even_with_following_content(self):
        body = ("<!-- wp:paragraph -->\n"
                '<p>Fonte: <a href="https://example.com">Sito ufficiale</a></p>\n'
                "<!-- /wp:paragraph -->"
                "<p>Il testo prosegue con una spiegazione editoriale.</p>")
        self.assertEqual(clean_source_links(body), ("<p>Il testo prosegue con una spiegazione editoriale.</p>", 1))

    def test_keeps_disclaimer_in_marked_paragraph(self):
        body = ('<p class="av-source-reference">Fonti: <a href="https://example.com">Scheda</a> e '
                '<a href="https://www.dday.it/redazione/prova">Prova</a>. '
                'AI Vision non ha eseguito misurazioni proprie.</p>')
        self.assertEqual(clean_source_links(body), ("<p>AI Vision non ha eseguito misurazioni proprie.</p>", 2))

    def test_unlinks_inline_source_but_preserves_attribution(self):
        body = ('<p>Per <a href="https://multiplayer.it/analisi">Multiplayer.it</a> la novità è rilevante. '
                '<a href="https://example.org/report?utm_source=x">L’autore</a> la descrive.</p>')
        self.assertEqual(
            clean_source_links(body, "https://example.org/report"),
            ("<p>Per Multiplayer.it la novità è rilevante. L’autore la descrive.</p>", 2),
        )

    def test_preserves_license_affiliate_and_tools(self):
        body = (
            '<figcaption>Foto: <a href="https://www.dday.it/foto">Credito</a></figcaption>'
            '<div class="av-amazon-affiliate"><a href="https://www.amazon.it/dp/B012345678?tag=test-21">Acquista</a></div>'
            '<h2>Prova lo strumento</h2><p>Apri il servizio.</p>'
            '<ul><li><a href="https://chatgpt.com/">ChatGPT</a></li></ul>'
        )
        self.assertEqual(clean_source_links(body, "https://chatgpt.com/"), (body, 0))

    def test_empty_content(self):
        self.assertEqual(clean_source_links(""), ("", 0))


if __name__ == "__main__":
    unittest.main()
