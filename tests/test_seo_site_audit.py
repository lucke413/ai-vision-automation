import unittest
from unittest.mock import patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import seo_site_audit as seo


def post(post_id, title, body, link=None):
    return {
        "id": post_id,
        "title": {"rendered": title}, "content": {"rendered": body},
        "excerpt": {"rendered": "<p>Riassunto</p>"},
        "link": link or ("https://aivision.altervista.org/articolo-" + str(post_id) + "/"),
        "slug": "articolo-" + str(post_id), "date": "2026-10-23T10:00:00",
        "featured_media": 3,
    }


class SeoSiteAuditTests(unittest.TestCase):
    def test_analyze_post_recognizes_links_images_and_shortness(self):
        p = post(1, "Come usare uno strumento AI per lavorare meglio",
                 '<h2>Passaggi</h2><p>Un test utile e leggibile.</p>'
                 '<a href="/pagina-correlata/">Leggi anche</a>'
                 '<a href="https://example.org/">Fonte</a>'
                 '<img src="x.png">')
        result = seo.analyze_post(p)
        self.assertEqual(result["in_content_internal_links"], 1)
        self.assertEqual(result["in_content_external_links"], 1)
        self.assertEqual(result["images_missing_alt"], 1)
        self.assertIn("very_short_body", result["warnings"])

    def test_meta_extraction_canonical_and_robots(self):
        page = seo.PageMeta()
        page.feed('<html lang="it-IT"><head><title>Titolo SEO</title>'
                  '<meta name="description" content="Descrizione chiara">'
                  '<link rel="canonical" href="https://aivision.altervista.org/post/">'
                  '<meta name="robots" content="index,follow">'
                  '<script type="application/ld+json">{}</script></head>'
                  '<body><h1>Articolo</h1></body></html>')
        self.assertEqual(page.meta["description"], "Descrizione chiara")
        self.assertEqual(page.canonical, "https://aivision.altervista.org/post/")
        self.assertEqual(page.headings["h1"], 1)
        self.assertEqual(page.structured_data, 1)

    def test_duplicate_warning_not_assumed_google_penalty(self):
        posts = [
            post(1, "OPPO Find X10 Pro Max nuove caratteristiche",
                 "<p>" + ("dettaglio " * 520) + "</p>"),
            post(2, "OPPO Find X10 Pro Max nuove fotocamere",
                 "<p>" + ("specifiche " * 520) + "</p>"),
        ]
        diagnostic = {"header_total": 2, "complete": True}
        live = {
            1: {"status": 200, "meta_description": "Info prodotto",
                "canonical": posts[0]["link"], "html_title": "SEO", "html_h1": 1,
                "json_ld_blocks": 1},
            2: {"status": 200, "meta_description": "Info fotocamere",
                "canonical": posts[1]["link"], "html_title": "SEO", "html_h1": 1,
                "json_ld_blocks": 1},
        }
        report = seo.build_report(posts, diagnostic, live, {})
        self.assertEqual(report["summary"]["total_posts"], 2)
        self.assertEqual(report["summary"]["html_findings"].get("noindex", 0), 0)
        self.assertIn("Search Console", report["limitations"][0])
        self.assertGreaterEqual(len(report["similar_titles"]), 1)

    def test_external_url_is_never_fetched(self):
        with self.assertRaises(ValueError):
            seo.get("https://evil.example/site")
        with self.assertRaises(ValueError):
            seo.get("http://aivision.altervista.org/")

    def test_wp_pagination_complete_without_guessing(self):
        class FakeResp:
            status_code = 200
            headers = {"X-WP-Total": "2"}
            def raise_for_status(self): pass
            def json(self): return [post(1, "Post A", "Testo"), post(2, "Post B", "Testo")]
        with patch.object(seo, "get", return_value=FakeResp()) as fetch:
            rows, info = seo.fetch_posts()
        self.assertEqual(len(rows), 2)
        self.assertTrue(info["complete"])
        self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
