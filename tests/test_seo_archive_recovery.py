import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import seo_archive_recovery as recovery


def post(post_id, title, body, excerpt="", modified="2026-10-01T12:00:00"):
    return {
        "id": post_id,
        "title": {"rendered": title},
        "content": {"rendered": body},
        "excerpt": {"rendered": excerpt},
        "date": "2026-10-01T12:00:00",
        "modified": modified,
        "link": f"https://aivision.altervista.org/example-{post_id}/",
        "slug": f"example-{post_id}",
        "featured_media": 42,
    }


class RecoveryTests(unittest.TestCase):
    def test_default_no_writes_and_classification(self):
        offer = post(4, "Samsung Galaxy Watch8 in offerta su Amazon", "<p>" + "prodotto " * 100 + "</p>")
        news = post(5, "Blender su Android per tablet nel 2027",
                    "<p>" + "Blender su Android per tablet nel 2027 avrà novità per la grafica digitale. " * 5 + "</p>")
        with tempfile.TemporaryDirectory() as folder, patch.object(
            recovery, "archive", return_value=([offer, news], {"complete": True})
        ), patch.object(recovery, "inspect_all_metadata", return_value={
            4: ({"description": ""}, None), 5: ({"description": ""}, None)
        }), patch.object(
            recovery, "apply_meta", side_effect=AssertionError("should never write")
        ):
            output = Path(folder) / "report.json"
            self.assertEqual(recovery.main(["--output", str(output)]), 0)
            report = json.loads(output.read_text())
        self.assertEqual(report["meta_updates_confirmed"], 0)
        self.assertEqual(report["mode"], "dry_run")
        self.assertEqual(len(report["posts"]), 2)
        self.assertEqual(report["posts"][1]["category_of_review"], "offerta_da_ricontrollare")

    def test_offers_not_extended_or_promoted_in_meta(self):
        item = post(
            9, "Samsung Galaxy Watch8 in offerta a 229 euro",
            "<p>Acquista subito Samsung Galaxy Watch8 con una promozione in offerta per oggi: "
            + "una descrizione abbastanza lunga sul prodotto disponibile in sconto. " * 5 + "</p>",
        )
        text, reason = recovery.description_from_existing(item)
        self.assertEqual(text, "")
        self.assertEqual(reason, "serve_redazione")

    def test_description_only_uses_existing_text(self):
        original = (
            "Blender su Android è in fase di sviluppo con una versione dedicata ai tablet "
            "prevista per la prima metà del 2027, secondo il programma reso noto dal progetto. "
            "L'applicazione punta a interfacce adatte al tocco."
        )
        item = post(7, "Blender su Android tablet 2027", f"<p>{original}</p>")
        description, source = recovery.description_from_existing(item)
        self.assertGreaterEqual(len(description), 85)
        self.assertLessEqual(len(description), 155)
        self.assertTrue(original.startswith(description))
        self.assertIn("corpo", source)

    def test_get_rejects_external_urls_even_with_matching_fragment(self):
        for url in ("https://fake.aivision.altervista.org/", "http://aivision.altervista.org/",
                    "https://attacker.example/aivision.altervista.org"):
            with self.assertRaises(ValueError):
                recovery.get(MagicMock(), url)

    def test_apply_requires_explicit_flag(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(PermissionError):
                recovery.main(["--apply-meta"])

    def test_apply_skips_changed_post_and_preserves_existing(self):
        row = {"id": 7, "url": "https://aivision.altervista.org/example-7/",
               "modified": "2026-10-01T12:00:00",
               "meta_description_proposal": "A long summary of a product article"}
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "status": "publish", "link": row["url"], "modified": row["modified"],
            "aivision_seo": {"seo_title": "Existing title", "seo_description": "Already set"}
        }
        with patch.object(recovery, "get", return_value=response):
            self.assertEqual(recovery.apply_meta(session, row, []),
                             "skipped_description_already_present")
        session.post.assert_not_called()

    def test_write_is_never_attempted_for_review_only_articles(self):
        row = {"id": 9, "url": "https://aivision.altervista.org/example-9/",
               "modified": "2026-10-01T12:00:00", "slug": "example-9",
               "title": "Samsung Galaxy Watch8 in offerta",
               "category_of_review": "offerta_da_ricontrollare",
               "meta_description_proposal": "Riassunto originale abbastanza lungo per SEO."}
        session = MagicMock()
        self.assertEqual(recovery.apply_meta(session, row, []),
                         "skipped_editorial_review")
        session.post.assert_not_called()

    def test_apply_only_missing_description_and_saves_backup_before_post(self):
        row = {"id": 7, "url": "https://aivision.altervista.org/example-7/",
               "modified": "2026-10-01T12:00:00", "slug": "example-7",
               "title": "Blender su Android per tablet",
               "category_of_review": "approfondimento_con_fonti",
               "meta_description_proposal": "Blender su Android è in sviluppo per tablet."}
        session = MagicMock()
        before = MagicMock()
        before.json.return_value = {
            "status": "publish", "link": row["url"], "slug": row["slug"],
            "modified": row["modified"],
            "title": {"rendered": row["title"]},
            "aivision_seo": {"seo_title": "Titolo conservato",
                             "focus_keyphrase": "Blender tablet", "seo_description": ""}
        }
        after = MagicMock()
        after.json.return_value = {"aivision_seo": {
            "seo_title": "Titolo conservato", "focus_keyphrase": "Blender tablet",
            "seo_description": row["meta_description_proposal"]
        }}
        session.post.return_value = after
        with patch.object(recovery, "get", return_value=before), patch.object(
            recovery, "_save_backup"
        ) as backup:
            self.assertEqual(recovery.apply_meta(session, row, []), "updated")
        backup.assert_called_once()
        self.assertEqual(session.post.call_args.kwargs["json"],
                         {"aivision_seo": {"seo_description": row["meta_description_proposal"]}})

    def test_missing_meta_in_long_post_is_not_ignored(self):
        short = post(1, "Blender su Android tablet 2027",
                     "<p>Blender su Android per tablet nel 2027 avrà novità per la grafica digitale. " * 2 + "</p>")
        long = post(2, "Notizie tecnologiche dettagliate di ottobre 2026",
                    "<p>Notizie tecnologiche dettagliate di ottobre 2026 spiegate chiaramente. " * 90 + "</p>")
        with tempfile.TemporaryDirectory() as folder, patch.object(
            recovery, "archive", return_value=([short, long], {"complete": True})
        ), patch.object(recovery, "inspect_all_metadata", return_value={
            1: ({"description": "Esistente"}, None),
            2: ({"description": ""}, None)
        }):
            result = Path(folder) / "report.json"
            self.assertEqual(recovery.main(["--output", str(result)]), 0)
            data = json.loads(result.read_text())
        self.assertEqual(data["meta_missing_outside_short_posts"], 1)
        self.assertEqual(data["meta_missing_count"], 1)


if __name__ == "__main__":
    unittest.main()
