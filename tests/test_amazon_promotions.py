import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

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
        self.assertIn("Prezzo verificato e valido al momento della pubblicazione", body)
        self.assertEqual(body, promos.expire_in_body(body, self.now))
        archive = promos.expire_in_body(body, self.now + timedelta(hours=4))
        self.assertIn("Introduzione", archive)
        self.assertNotIn("59,90", archive)
        self.assertNotIn("amazon.it/dp", archive)

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
                patch.object(promos.CreatorsAPI, "shortlist", return_value=[(promos.CATEGORIES[0], deal)]), \
                patch.object(promos, "publish_edition", return_value={}) as publish:
            promos.run(object(), object(), self.now)
        publish.assert_not_called()
        self.assertTrue(promos.belongs_to_campaign(deal, campaign))
        other_campaign = promos.replace(campaign, title="Prime Day")
        self.assertFalse(promos.belongs_to_campaign(deal, other_campaign))

    def test_two_distinct_multicategory_editions_and_separate_books(self):
        from datetime import datetime
        from unittest.mock import Mock
        now = datetime.now(promos.get_timezone())
        campaign = promos.Offer("bf", "Eventi", "Black Friday", "", "", "", "", now + timedelta(days=2),
                                starts=now - timedelta(days=1))
        sale = promos.replace(campaign, key="ebook-kindle", category="Lettura digitale", starts=None)
        catalog = Mock()
        def shortlist(stamp, event, categories):
            badge = "Black Friday" if event else "Mese della Lettura"
            return [(category, promos.replace(campaign, key=f"{category.title}-{i}", category=category.title,
                                              title=f"{category.title}-{i}", campaign_badge=badge, starts=None))
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
             patch.object(promos, "publish_edition", side_effect=publish):
            promos.run(None, None, now)
        self.assertEqual(len(pages), 3)
        import re
        items = [set(re.findall(r"<h4>(.*?)</h4>", body)) for _, body in pages]
        self.assertTrue(all(len(group) >= 20 for group in items))
        self.assertTrue(items[0].isdisjoint(items[1]))
        self.assertIn("Cucina", pages[0][1])
        self.assertIn("Fantasy", pages[2][1])
        self.assertNotIn("Cucina", pages[2][1])


if __name__ == "__main__":
    unittest.main()
