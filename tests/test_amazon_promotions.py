import sys
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import amazon_promotions as promos


class AmazonPromotionsTests(unittest.TestCase):
    def setUp(self):
        self.now = promos.local_at(date(2026, 11, 19), 12)
        self.tag = "lavocdelweb-21"
        self.product = {
            "asin": "B012345678",
            "detailPageURL": f"https://www.amazon.it/dp/B012345678?tag={self.tag}",
            "itemInfo": {"title": {"displayValue": "Modello X cuffie Bluetooth"}},
            "images": {"primary": {"medium": {
                "url": "https://m.media-amazon.com/images/I/modello-x.jpg",
                "width": 160, "height": 122,
            }}},
            "offersV2": {"listings": [{
                "isBuyBoxWinner": True,
                "availability": {"type": "IN_STOCK"},
                "condition": {"value": "New"},
                "dealDetails": {"accessType": "PRIME_EXCLUSIVE", "badge": "Black Friday Deal",
                                "endTime": (self.now + timedelta(hours=8)).isoformat()},
                "price": {"money": {"currency": "EUR", "amount": 59.9},
                          "savings": {"percentage": 20}},
            }]},
        }

    def test_black_friday_times_and_local_label(self):
        window = promos.dated_campaign(
            "La Settimana del Black Friday inizierà alle 00:01 del 19 novembre e durerà fino alle 23:59 del 30 novembre 2026",
            self.now.date(),
        )
        self.assertEqual(window, (promos.local_at(date(2026, 11, 19), 0, 1),
                                  promos.local_at(date(2026, 12, 1))))
        self.assertEqual(promos.italian_date(self.now.date()), "19 novembre 2026")

    def test_prices_from_exact_available_items_only(self):
        offer = promos.product_offer(self.product, promos.CATEGORIES[0], self.now, self.tag)
        self.assertEqual(offer.price, "59,90 €")
        self.assertEqual(offer.savings, 20)
        self.assertEqual(offer.image[1:], (160, 122))
        self.assertIn("Prime", offer.terms)
        listing = self.product["offersV2"]["listings"][0]
        listing["availability"]["type"] = "OUT_OF_STOCK"
        self.assertIsNone(promos.product_offer(self.product, promos.CATEGORIES[0], self.now, self.tag))
        listing["availability"]["type"] = "IN_STOCK"
        listing["dealDetails"]["endTime"] = (self.now + timedelta(minutes=30)).isoformat()
        self.assertIsNone(promos.product_offer(self.product, promos.CATEGORIES[0], self.now, self.tag))

    def test_archive_removes_expired_cta_and_price(self):
        deal = promos.product_offer(self.product, promos.CATEGORIES[0], self.now, self.tag)
        body = "<p>Introduzione</p>" + promos.render_offers([deal], self.now)
        self.assertIn("Scelte da AI Vision per voi", body)
        self.assertIn("Clicca qui per acquistarlo", body)
        self.assertIn('rel="sponsored nofollow"', body)
        self.assertIn("Prezzo 59,90 €", body)
        self.assertIn("Sconto 20%", body)
        self.assertIn("Verificato il 19/11/2026 alle 12:00", body)
        self.assertIn("verificati al momento della pubblicazione", body)
        self.assertGreater(body.index('id="aivision-amazon-price-note"'), body.index("Clicca qui per acquistarlo"))
        parsed = promos.BeautifulSoup(body, "html.parser")
        image = parsed.find("img")
        self.assertEqual(image["src"], self.product["images"]["primary"]["medium"]["url"])
        self.assertEqual(image["alt"], deal.title)
        self.assertEqual(image.parent["href"], deal.url)
        self.assertEqual(body, promos.expire_in_body(body, self.now))
        archive = promos.expire_in_body(body, self.now + timedelta(hours=4))
        self.assertIn("Introduzione", archive)
        self.assertNotIn("59,90", archive)
        self.assertNotIn("Sconto 20%", archive)
        self.assertNotIn("<img", archive)
        self.assertNotIn('id="aivision-amazon-price-note"', archive)
        self.assertNotIn("amazon.it/dp", archive)

    def test_refresh_uses_exact_product_and_preserves_editorial_copy_and_earlier_expiry(self):
        stamped = self.now + timedelta(minutes=3)
        self.product["images"]["primary"]["medium"]["url"] = "https://example.org/not-amazon.jpg"
        original = promos.Offer(self.product["asin"], "Casa e pulizia", "Titolo redazionale", "Descrizione originale",
                                "Consiglio originale", "", self.product["detailPageURL"],
                                self.now + timedelta(hours=1), affiliate=True)
        api = Mock(tag=self.tag)
        api.get_products.return_value = [self.product]
        with patch.object(promos, "datetime", wraps=datetime) as clock:
            clock.now.return_value = stamped
            refreshed, = promos.refresh_products(api, [original], None, None)
        api.get_products.assert_called_once_with([original.key])
        self.assertEqual(refreshed.description, original.description)
        self.assertEqual(refreshed.expires, original.expires)
        self.assertEqual(refreshed.verified_at, stamped)
        self.assertEqual(refreshed.savings, 20)
        self.assertIsNone(refreshed.image)

    def test_audible_uses_the_exact_public_offer_and_accepts_campaign_link(self):
        text = ("I clienti idonei possono ottenere tre mesi di abbonamento Audible Premium a soli 0,99€ al mese. "
                "L’offerta è valida fino al 28 dicembre 2026, con rinnovo automatico al prezzo mensile di 9,99€.")
        offer, = promos.service_offers(text, date(2026, 11, 3), self.now, self.tag, {})
        self.assertEqual(offer.price, "0,99 € al mese")
        self.assertFalse(offer.affiliate)
        with_link, = promos.service_offers(
            text, date(2026, 11, 3), self.now, self.tag, {"audible": "https://amzn.to/codice-campagna"}
        )
        self.assertTrue(with_link.affiliate)
        self.assertFalse(list(promos.service_offers(
            text, date(2026, 11, 3), self.now + timedelta(days=60), self.tag, {}
        )))

    def test_titles_cover_labels_and_intro_for_daily_black_friday_edition(self):
        deal = promos.product_offer(self.product, promos.CATEGORIES[0], self.now, self.tag)
        campaign = promos.Offer("black-friday", "Evento", "Black Friday", "Introduzione", "Consiglio", "",
                                "https://www.amazon.it/blackfriday", self.now + timedelta(days=5),
                                starts=self.now - timedelta(hours=2))
        with patch.dict(promos.os.environ, {"AMAZON_CREATORS_CREDENTIAL_ID": "test",
                                           "AMAZON_CREATORS_CREDENTIAL_SECRET": "test"}), \
                patch.object(promos, "newsroom_offers", return_value=[campaign]), \
                patch.object(promos, "editorial_offers", return_value={}), \
                patch.object(promos.CreatorsAPI, "shortlist", return_value=[(promos.CATEGORIES[0], deal)]), \
                patch.object(promos.CreatorsAPI, "verify", return_value=[deal]), \
                patch.object(promos.PublicDeals, "shortlist", return_value=[]), \
                patch.object(promos, "publish_edition", return_value={}) as publish:
            report = promos.run(Mock(existing_post=lambda slug: None), object(), self.now)
        publish.assert_not_called()
        self.assertEqual(report["status"], "partial_or_blocked")
        self.assertTrue(promos.belongs_to_campaign(deal, campaign))
        other_campaign = promos.replace(campaign, title="Prime Day")
        self.assertFalse(promos.belongs_to_campaign(deal, other_campaign))

    def test_append_new_asins_only(self):
        offer = promos.product_offer(self.product, promos.CATEGORIES[0], self.now, self.tag)
        body = promos.render_offers([offer], self.now)
        post = {"id": 12, "status": "publish", "slug": "black-friday", "link": "example", "content": {"raw": body}}
        client = Mock()
        client.session.get.return_value.json.return_value = post
        extra = promos.replace(offer, key="B012345679", url=offer.url.replace(offer.key, "B012345679"))
        self.assertEqual(promos.extend_edition(client, post, [offer, extra], self.now)["status"], "updated")
        saved = client.session.post.call_args.kwargs["json"]["content"]
        self.assertTrue(saved.startswith(promos.PRICE_NOTE.sub("", body)))
        self.assertEqual(saved.count('id="aivision-amazon-price-note"'), 1)
        self.assertEqual(saved.count(offer.key), 1)
        self.assertEqual(saved.count(extra.key), 1)

    def test_public_card_needs_a_product_price_and_matching_campaign(self):
        source = promos.PublicDeals(None, self.tag, promos.AMAZON + "/blackfriday")
        markup = ('<div data-asin="B0DD2HYX6L"><a href="/dp/B0DD2HYX6L"><h2>Ember QLED</h2></a>'
                  '<span class="a-price"><span class="a-offscreen">249,99 €</span></span>'
                  '<span class="dealBadge">Black Friday Big Deal</span></div>')
        with patch.object(source, "page", return_value=promos.BeautifulSoup(markup, "html.parser")):
            rows = source.shortlist(self.now, None, promos.CATEGORIES)
            self.assertEqual(len(rows), 1)
            offer = rows[0][1]
            self.assertIn("tag=lavocdelweb-21", offer.url)
            self.assertEqual(offer.category, "TV e home cinema")
            self.assertFalse(source.shortlist(self.now, promos.replace(offer, title="Prime Day"), promos.CATEGORIES))
        with patch.object(source, "page", return_value=promos.BeautifulSoup("", "html.parser")):
            self.assertFalse(source.verify(rows, self.now))

    def test_two_distinct_multicategory_editions_and_separate_books(self):
        from datetime import datetime
        from unittest.mock import Mock
        now = datetime.now(promos.get_timezone())
        campaign = promos.Offer("bf", "Eventi", "Black Friday", "", "", "", "", now + timedelta(days=2),
                                starts=now - timedelta(days=1))
        sale = promos.replace(campaign, key="ebook-kindle", category="Lettura digitale", starts=None)
        catalog = Mock()
        def shortlist(stamp, event, categories):
            badge = "Black Friday" if event else "Mese della Lettura" if categories == promos.BOOKS else "Offerta"
            return [(category, promos.replace(campaign, key=f"{badge}-{category.title}-{i}", category=category.title,
                                              title=f"{badge}-{category.title}-{i}", campaign_badge=badge, starts=None))
                    for category in categories for i in range(6)]
        catalog.shortlist.side_effect = shortlist
        catalog.verify.side_effect = lambda rows, *args: [offer for _, offer in rows]
        pages = []
        def publish(client, session, title, slug, intro, scene, label, check):
            pages.append((slug, check()))
            return {"status": "planned"}
        with patch.dict(promos.os.environ, {"AMAZON_CREATORS_CREDENTIAL_ID":"test",
                                           "AMAZON_CREATORS_CREDENTIAL_SECRET":"test"}), \
             patch.object(promos, "CreatorsAPI", return_value=catalog), \
             patch.object(promos, "newsroom_offers", return_value=[campaign, sale]), \
             patch.object(promos, "editorial_offers", return_value={}), \
             patch.object(promos, "publish_edition", side_effect=publish):
            promos.run(Mock(existing_post=lambda slug: None), None, now)
        self.assertEqual(len(pages), 4)
        import re
        items = [set(re.findall(r"<h4>(.*?)</h4>", body)) for _, body in pages]
        self.assertTrue(all(len(group) >= 20 for group in items))
        self.assertTrue(items[0].isdisjoint(items[1]))
        self.assertIn("Cucina", pages[0][1])
        self.assertTrue(pages[2][0].startswith("offerte-amazon-del-giorno"))
        self.assertIn("Fantasy", pages[3][1])
        self.assertNotIn("Cucina", pages[3][1])

    def test_editorial_feed_can_publish_three_editions_without_a_catalog(self):
        from datetime import datetime

        now = datetime.now(promos.get_timezone())
        expiry = (now + timedelta(hours=4)).isoformat()
        categories = ("Casa e pulizia", "Cucina", "Audio", "Bellezza")

        def group(kind, start, length):
            products = [{"url": f"https://www.amazon.it/dp/B{i:09d}?tag=diverso-21",
                         "category": categories[i % len(categories)], "title": f"Modello {i}",
                         "description": f"Caratteristiche del modello {i}", "why": "Controlla le misure"}
                        for i in range(start, start + length)]
            return {"kind": kind, "checked_at": now.isoformat(), "expires_at": expiry,
                    "products": [*products, products[0]]}

        def publish(client, session, title, slug, intro, scene, label, content):
            bodies.append(content())
            return {"status": "planned"}

        bodies = []
        with tempfile.TemporaryDirectory() as folder:
            feed = Path(folder) / "offers.json"
            feed.write_text(json.dumps([group("black-friday", 1, 40), group("daily", 41, 20)]), encoding="utf-8")
            with patch.object(promos, "EDITORIAL_FEED", feed), \
                    patch.object(promos, "newsroom_offers", return_value=[]), \
                    patch.object(promos, "PublicDeals") as public, \
                    patch.object(promos, "CreatorsAPI") as creators, \
                    patch.object(promos, "publish_edition", side_effect=publish):
                report = promos.run(Mock(existing_post=lambda slug: None), None, now)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["editorial_candidates"], {"black-friday": 40, "daily": 20})
        self.assertEqual([x["editorial_products"] for x in report["editions"]], [20, 20, 20])
        self.assertEqual([body.count("tag=lavocdelweb-21") for body in bodies], [20, 20, 20])
        self.assertFalse(any("diverso-21" in body or "€" in body for body in bodies))
        public.assert_not_called()
        creators.return_value.shortlist.assert_not_called()

    def test_editorial_feed_filters_expired_entries_and_inappropriate_urls(self):
        now = self.now
        group = {"kind": "daily", "checked_at": (now - timedelta(hours=1)).isoformat(),
                 "expires_at": (now + timedelta(hours=4)).isoformat(),
                 "products": [{"url": "https://www.amazon.it/deals", "category": "Cucina",
                               "title": "Prodotto", "description": "Descrizione", "why": "Utilità"}]}
        expired = {**group, "expires_at": now.isoformat()}
        warnings = []
        with tempfile.TemporaryDirectory() as folder:
            feed = Path(folder) / "offers.json"
            feed.write_text(json.dumps([expired, group]), encoding="utf-8")
            with patch.object(promos, "EDITORIAL_FEED", feed):
                offers = promos.editorial_offers(now, self.tag, warnings)
        self.assertEqual(offers, {"daily": {}})
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main()
