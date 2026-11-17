import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import legacy_content_repair as repair


def post(post_id=9000, title="Articolo di prova", body=None, date_value="2026-10-01T10:00:00"):
    body = body or ("<p>Contenuto editoriale informativo. " + "dettaglio " * 100 + "</p>")
    return {
        "id": post_id,
        "title": {"raw": title, "rendered": title},
        "content": {"raw": body, "rendered": body},
        "excerpt": {"rendered": ""},
        "link": f"https://aivision.altervista.org/post-{post_id}/",
        "slug": f"post-{post_id}",
        "date": date_value,
        "modified": date_value,
        "featured_media": 0,
    }


class LegacyContentRepairTests(unittest.TestCase):
    def test_price_notice_uses_published_date_and_is_marked(self):
        note = repair.price_notice("2026-10-01T10:00:00")
        self.assertIn(repair.NOTICE_MARKER, note)
        self.assertIn("1 ottobre 2026", note)
        self.assertIn("possono essere cambiate", note)

    def test_old_offer_gets_notice_but_regular_product_news_does_not(self):
        today = date(2026, 11, 16)
        old_offer = post(title="Smartphone in offerta a 399 euro")
        plan = repair.build_plan([old_offer], today)
        self.assertEqual(len(plan), 1)
        self.assertIn(repair.NOTICE_MARKER, plan[0]["new_content"])
        self.assertIn("stale_offer_notice", plan[0]["reasons"])

        regular = post(title="Nuovo smartphone: caratteristiche e specifiche")
        self.assertEqual(repair.build_plan([regular], today), [])

    def test_review_title_is_repaired_with_source_and_disclosure(self):
        today = date(2026, 11, 16)
        original = post(post_id=478, title="iPhone 18 Pro: recensione e novità")
        plan = repair.build_plan([original], today)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["new_title"], repair.REVIEW_REPAIRS[478]["title"])
        self.assertIn("apple.com", plan[0]["new_content"])
        self.assertIn(repair.REPAIR_MARKER, plan[0]["new_content"])

    def test_known_near_copy_is_rewritten_and_receives_original_cover(self):
        today = date(2026, 11, 16)
        original = post(post_id=1753, title="Recensione Anker MagGo Power Bank 2 Pro")
        plan = repair.build_plan([original], today)
        self.assertEqual(len(plan), 1)
        self.assertIn("Qi2.2", plan[0]["new_title"])
        self.assertIn("AI Vision non ha eseguito test", plan[0]["new_content"])
        self.assertEqual(plan[0]["cover_category"], "Accessori e postazioni")

    def test_full_backup_contains_every_published_post_not_only_repair_targets(self):
        first = post(post_id=9001, title="Articolo ordinario")
        second = post(post_id=9002, title="Altro articolo")
        plan = repair.build_plan([first, second], date(2026, 11, 16))
        backup = repair.build_full_backup([first, second], plan, "apply")

        self.assertTrue(backup["backup_complete"])
        self.assertEqual(backup["backup_type"], "full_published_posts_snapshot")
        self.assertEqual(backup["total_posts_scanned"], 2)
        self.assertEqual(backup["total_posts_backed_up"], 2)
        self.assertEqual([item["id"] for item in backup["posts"]], [9001, 9002])
        self.assertEqual(backup["posts"][0]["title"], "Articolo ordinario")
        self.assertTrue(backup["snapshot_sha256"])

    def test_backup_persistence_is_atomic_and_keeps_original_content(self):
        import json
        import tempfile
        from unittest.mock import patch

        original = post(post_id=9003, title="Originale")
        backup = repair.build_full_backup([original], [], "dry_run")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "backup.json"
            with patch.object(repair, "OUTPUT", destination):
                repair.persist_backup(backup)
            saved = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(saved["posts"][0]["title"], "Originale")
            self.assertEqual(saved["posts"][0]["content"], original["content"]["raw"])
            self.assertFalse(destination.with_suffix(".json.tmp").exists())

    def test_repair_is_idempotent(self):
        today = date(2026, 11, 16)
        original = post(post_id=478, title="iPhone 18 Pro: recensione")
        first = repair.build_plan([original], today)[0]
        repaired = post(
            post_id=478,
            title=first["new_title"],
            body=first["new_content"],
            date_value=original["date"],
        )
        self.assertEqual(repair.build_plan([repaired], today), [])


if __name__ == "__main__":
    unittest.main()
