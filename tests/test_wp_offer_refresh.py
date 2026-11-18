import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from amazon_promotions import editorial_picks, local_at, picks_section
from wp_offer_refresh import media_changes, strip_credit


class OfferRefreshTests(unittest.TestCase):
    def test_only_standalone_credit_is_removed(self):
        value = ('<figure><img src="photo.jpg"><figcaption class="wp-element-caption">'
                 'Illustrazione <em>generata con IA</em></figcaption></figure>'
                 '<figcaption>Foto: Wikimedia Commons · CC BY-SA</figcaption>'
                 '<p>Il testo cita “Illustrazione generata con IA” come esempio.</p>')
        result = strip_credit(value)
        self.assertEqual(result, '<figure><img src="photo.jpg"></figure>'
                         '<figcaption>Foto: Wikimedia Commons · CC BY-SA</figcaption>'
                         '<p>Il testo cita “Illustrazione generata con IA” come esempio.</p>')
        self.assertEqual(strip_credit(result), result)

    def test_attachment_caption_can_be_removed_without_replacing_alt(self):
        media = {"caption": {"raw": "Illustrazione generata con IA"}, "description": {"raw": ""},
                 "alt_text": "Copertina con libri e cuffie"}
        self.assertEqual(media_changes(media), {"caption": ""})

    def test_each_curated_pick_has_one_direct_link_and_reason(self):
        now = local_at(date(2026, 11, 18), 15)
        offers = editorial_picks("reading-2026-11", now, "lavocdelweb-21")
        self.assertEqual(len(offers), 3)
        body = picks_section(offers, now)
        self.assertEqual(body.count("/dp/"), 3)
        self.assertEqual(body.count("tag=lavocdelweb-21"), 3)
        self.assertEqual(body.count("Perché comprarlo"), 3)
        self.assertEqual(body.count("Mini recensione"), 3)
        self.assertNotIn("Prezzo verificato", body)
        self.assertFalse(editorial_picks("reading-2026-11", local_at(date(2026, 12, 1)), "lavocdelweb-21"))


if __name__ == "__main__":
    unittest.main()
