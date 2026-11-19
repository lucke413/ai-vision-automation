import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import article_generator as generator
import wp_publisher as publisher

from scripts.amazon_affiliate import DISCLOSURE, affiliate_section, ensure_article_tracking, article_products, product_asin, tracking_tag


TEST_TAG = "aivision-test-21"


class AmazonAffiliateTests(unittest.TestCase):
    def test_final_tracking_for_every_article(self):
        source = '<!-- wp:paragraph --><p>News</p><!-- /wp:paragraph -->'
        result = ensure_article_tracking(source, TEST_TAG)
        self.assertEqual(result, source)
        wrong = '<a href="https://www.amazon.it/dp/B0DD2HYX6L?tag=other-21&amp;th=1">TV</a>'
        result = ensure_article_tracking(wrong, TEST_TAG)
        self.assertNotIn("other-21", result)
        self.assertIn("tag=" + TEST_TAG, result)
        self.assertNotIn("/deals", result)
        self.assertIn("th=1", result)

    def setUp(self):
        self.draft = {
            "title": "Sony WH-CH730N: cosa sapere sulle cuffie",
            "body_markdown": "Le Sony WH-CH730N hanno diversi controlli sulle cuffie.",
            "amazon_products": ["Sony WH-CH730N"],
            "amazon_source_links": [{
                "url": "https://www.amazon.it/Sony-Cuffie/dp/B012345678?tag=altra-fonte-21",
                "label": "Acquista Sony WH-CH730N su Amazon",
            }],
        }

    def test_product_link_uses_own_tag_and_disclosure(self):
        block, status, links = affiliate_section(self.draft, "<p>Testo</p>", TEST_TAG)
        self.assertEqual(status, "inserted")
        self.assertEqual(links, [{"product": "Sony WH-CH730N", "type": "product", "asin": "B012345678"}])
        self.assertIn("https://www.amazon.it/dp/B012345678?tag=aivision-test-21", block)
        self.assertNotIn("altra-fonte-21", block)
        self.assertIn("Clicca qui per acquistarlo su Amazon", block)
        self.assertIn(DISCLOSURE, block)
        self.assertIn('rel="sponsored nofollow"', block)

    def test_roundup_gives_each_exact_model_its_own_card(self):
        models = [f"Marca Modello {n}" for n in range(1, 5)]
        draft = {
            "title": "Promozioni Marca",
            "body_markdown": ". ".join(models),
            "amazon_products": models,
            "amazon_source_links": [{"label": model, "url": f"https://www.amazon.it/dp/B01234567{n}"}
                                    for n, model in enumerate(models)],
            "amazon_product_notes": [
                {"product": model, "summary": "La scheda descrive un dispositivo da viaggio.",
                 "why": "Utile quando serve una soluzione compatta."} for model in models
            ],
        }
        block, status, links = affiliate_section(draft, "<p>Testo</p>", TEST_TAG)
        self.assertEqual(status, "inserted")
        self.assertEqual(len(links), 4)
        self.assertEqual(block.count("Mini recensione"), 4)
        self.assertEqual(block.count("Perché comprarlo"), 4)
        self.assertEqual(block.count("/dp/"), 4)

    def test_unknown_or_ambiguous_asin_uses_labelled_search(self):
        self.draft["amazon_source_links"].append({
            "label": "Sony WH-CH730N", "url": "https://www.amazon.it/dp/B987654321"
        })
        block, status, links = affiliate_section(self.draft, "<p>Testo</p>", TEST_TAG)
        self.assertEqual(status, "inserted")
        self.assertEqual(links[0]["type"], "search")
        self.assertIn("https://www.amazon.it/s?k=Sony+WH-CH730N&amp;tag=aivision-test-21", block)
        self.assertIn("Cerca questo modello su Amazon", block)
        self.assertNotIn("acquistarlo", block)

    def test_model_requires_article_and_source_evidence(self):
        self.assertEqual(article_products(self.draft, source="Cuffie Sony WH-CH720N"), [])
        self.assertEqual(article_products(self.draft, source="Prova delle Sony WH-CH730N"), ["Sony WH-CH730N"])
        variant = {"title": "Xiaomi 18 Pro Max in Italia", "amazon_products": ["Xiaomi 18 Pro"]}
        self.assertEqual(article_products(variant, source=variant["title"]), [])

    def test_product_news_with_empty_metadata_gets_exact_variant_search(self):
        model = "MX Master 4 Creator Edition"
        draft = {
            "title": f"{model}: estetica rinnovata per il mouse Logitech",
            "body_markdown": f"Il mouse Logitech {model} ha una finitura diversa.",
            "amazon_products": [],
            "amazon_source_links": [{"label": "Logitech MX Master 4 per Mac",
                                     "url": "https://www.amazon.it/dp/B0FHHV7BTG"}],
        }
        self.assertEqual(article_products(draft, source=f"Il nuovo mouse {model}"), [model])
        self.assertEqual(article_products(draft, source="Mouse MX Master 4 per Mac"), [])
        block, status, links = affiliate_section(draft, "<p>Testo</p>", TEST_TAG)
        self.assertEqual(status, "inserted")
        self.assertEqual(links[0]["type"], "search")
        self.assertIn(f"k=MX+Master+4+Creator+Edition&amp;tag={TEST_TAG}", block)
        self.assertNotIn("B0FHHV7BTG", block)

    def test_variant_in_title_and_excerpt_recovers_separate_mentions_in_saved_article(self):
        draft = {
            "title": "MX Master 4 Creator Edition: il mouse Logitech",
            "excerpt": "Scopriamo la MX Master 4 Creator Edition di Logitech.",
            "body_markdown": "Il mouse MX Master 4 è la base. La Creator Edition cambia i colori.",
        }
        self.assertEqual(article_products(draft, draft["title"]), ["MX Master 4 Creator Edition"])
        self.assertEqual(article_products({**draft, "excerpt": ""}), [])

    def test_subscription_and_vehicle_do_not_add_incidental_products(self):
        subscription = {"title": "GTA Plus gratis con GTA 6: l'abbonamento",
                        "cover_subject": "GTA 6", "body_markdown": "GTA 6 arriva su console."}
        vehicle = {"title": "Kymco People R Hybrid porta l'ibrido sugli scooter",
                   "body_markdown": "Kymco People R Hybrid è uno scooter.",
                   "amazon_products": ["Kymco People R Hybrid"]}
        self.assertEqual(article_products(subscription), [])
        self.assertEqual(article_products(vehicle), [])

    def test_does_not_guess_canonical_links_or_use_platform_tag(self):
        self.assertEqual(product_asin("https://amazon.it.example.org/dp/B012345678"), "")
        self.assertEqual(product_asin("https://www.amazon.it/s?k=B012345678"), "")
        self.assertEqual(tracking_tag("https://www.amazon.it/dp/B012345678?tag=gz-blog-21"), "")
        self.assertEqual(tracking_tag("https://www.amazon.it/dp/B012345678?tag=aivision-test-21"), TEST_TAG)
        self.assertEqual(affiliate_section(self.draft, "<p>Testo</p>", "")[1], "tracking_id_missing")

    def test_preserves_existing_link_and_gates_amazon_prices(self):
        existing = '<p><a href="https://www.amazon.it/dp/B012345678?tag=existing-21">Offerta</a></p>'
        self.assertEqual(affiliate_section(self.draft, existing, TEST_TAG)[1], "already_present")
        self.draft["body_markdown"] += " Su Amazon costano 79 €."
        self.assertEqual(affiliate_section(self.draft, "<p>Testo</p>", TEST_TAG)[1], "amazon_price_in_article")

    def test_source_parser_only_collects_links_in_article(self):
        parser = generator.SourceArticleParser()
        parser.feed('<main><article><nav><a href="https://www.amazon.it/dp/B987654321">Menu</a></nav>'
                    '<p><a href="https://www.amazon.it/dp/B012345678">Sony <b>WH-CH730N</b></a></p>'
                    '</article></main>')
        self.assertEqual(parser.amazon_links, [{
            "label": "Sony WH-CH730N", "url": "https://www.amazon.it/dp/B012345678"
        }])

    def test_publisher_adds_affiliate_link_to_wordpress_payload(self):
        client = publisher.WordPressClient("https://example.com", "", "", dry_run=True)
        client.create_post = MagicMock(return_value={"status": "planned"})
        draft = {**self.draft, "body_markdown": self.draft["body_markdown"] + " " + " ".join(["contenuto"] * 600)}
        with patch.dict(os.environ, {"AMAZON_ASSOCIATE_TAG": TEST_TAG}):
            result = publisher.publish_one(draft, datetime.now(timezone.utc), client, client.session)
        content = client.create_post.call_args.args[0]["content"]
        self.assertIn(DISCLOSURE, content)
        self.assertIn('rel="sponsored nofollow"', content)
        self.assertEqual(result["amazon_affiliate_status"], "inserted")


if __name__ == "__main__":
    unittest.main()
