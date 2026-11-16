import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import editorial_content_audit as audit


def post(title, body, *, date_value="2026-10-01T10:00:00", featured=12, url="https://aivision.altervista.org/test/"):
    return {
        "id": 1,
        "title": {"rendered": title},
        "content": {"rendered": body},
        "excerpt": {"rendered": "<p>Estratto editoriale di prova.</p>"},
        "link": url,
        "slug": "test",
        "date": date_value,
        "modified": date_value,
        "featured_media": featured,
    }


class EditorialContentAuditTests(unittest.TestCase):
    def test_stale_offer_is_flagged_but_historical_offer_is_not(self):
        current = date(2026, 11, 16)
        stale = audit.analyze_post(post(
            "Offerta Amazon: sconto su smartphone",
            "<p>Il prodotto è disponibile ora a prezzo speciale. " + "dettaglio " * 80 + "</p>",
        ), current)
        self.assertIn("stale_offer_review", {x["code"] for x in stale["flags"]})

        historical = audit.analyze_post(post(
            "Offerta Amazon di ottobre: prezzo e caratteristiche",
            "<p>La promozione era disponibile fino al 20 ottobre e si è conclusa. " + "dettaglio " * 80 + "</p>",
        ), current)
        self.assertNotIn("stale_offer_review", {x["code"] for x in historical["flags"]})

    def test_generic_product_offering_and_price_tracking_are_not_stale_promotions(self):
        current = date(2026, 11, 16)
        product_launch = audit.analyze_post(post(
            "Nuance Audio Plus: gli occhiali acustici arrivano in Italia da 899 euro",
            "<p>Il produttore amplia la propria offerta di tecnologia assistiva. " + "dettaglio " * 80 + "</p>",
        ), current)
        self.assertNotIn("stale_offer_review", {x["code"] for x in product_launch["flags"]})

        price_tracking = audit.analyze_post(post(
            "Safari introduce una funzione per monitorare prezzi e contenuti web",
            "<p>La funzione permette di controllare le variazioni dei prezzi nel tempo. " + "dettaglio " * 80 + "</p>",
        ), current)
        self.assertNotIn("stale_offer_review", {x["code"] for x in price_tracking["flags"]})

    def test_recent_news_about_last_hours_is_not_an_expired_offer(self):
        result = audit.analyze_post(post(
            "Account PlayStation a rischio hacker: come proteggersi",
            "<p>Nelle ultime ore sono emersi nuovi tentativi di phishing. " + "dettaglio " * 80 + "</p>",
            date_value="2026-10-06T10:00:00",
        ), date(2026, 11, 16))
        self.assertNotIn("likely_expired_promo", {x["code"] for x in result["flags"]})

    def test_internal_and_external_links_are_counted(self):
        body = (
            '<p>Un testo abbastanza lungo per verificare i collegamenti. ' + "contenuto " * 70 +
            '<a href="https://aivision.altervista.org/altro-articolo/">Approfondimento</a> '
            '<a href="https://example.com/fonte">Fonte</a></p>'
        )
        result = audit.analyze_post(post("Articolo di tecnologia", body), date(2026, 11, 16))
        self.assertEqual(result["internal_links"], 1)
        self.assertEqual(result["external_links"], 1)
        self.assertNotIn("no_internal_links", {x["code"] for x in result["flags"]})
        self.assertNotIn("no_external_references", {x["code"] for x in result["flags"]})

    def test_editorial_notes_and_affiliate_claims_are_flagged(self):
        body = "<p>Prima della pubblicazione serve un fact-check. I link affiliati potrebbero generare una commissione. " + "testo " * 100 + "</p>"
        result = audit.analyze_post(post("Guida tecnologica", body), date(2026, 11, 16))
        codes = {x["code"] for x in result["flags"]}
        self.assertIn("editorial_note_in_public_text", codes)
        self.assertIn("affiliate_disclosure_check", codes)

    def test_similar_body_detector_finds_near_duplicate_articles(self):
        words = " ".join(f"termine{index}" for index in range(350))
        first = {"id": 1, "title": "Primo articolo", "url": "https://aivision.altervista.org/a/", "words": 350, "body_text": words}
        second = {"id": 2, "title": "Secondo articolo", "url": "https://aivision.altervista.org/b/", "words": 350, "body_text": words}
        matches = audit.find_similar_bodies([first, second])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["fivegram_jaccard"], 1.0)


if __name__ == "__main__":
    unittest.main()
