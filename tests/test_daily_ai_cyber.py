import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ai_cyber
import article_generator as generator
import daily_selector as selector
import history_filter as history
import wp_publisher as publisher


def item(index, topic=""):
    return {
        "title": f"Una scelta editoriale distinta numero {index}",
        "url": f"https://example.com/story-{index}",
        "article_id": f"item-{index}",
        "category": "Tecnologia" if not topic else "Sicurezza",
        "story_type": "ANALISI",
        **({ai_cyber.TOPIC_KEY: topic} if topic else {}),
    }


class DailyAICyberTests(unittest.TestCase):
    def test_topic_requires_the_intersection(self):
        self.assertEqual(ai_cyber.topic_for("Microsoft announces an AI subscription"), "")
        self.assertEqual(ai_cyber.topic_for("Customer credentials exposed in data breach"), "")
        self.assertEqual(ai_cyber.topic_for("Access permissions on AI coding agents"), "identita-e-permessi")
        self.assertEqual(ai_cyber.topic_for("AI voice cloning used in phishing"), "impersonificazione")

    def test_extra_slot_preserves_six_ordinary_stories_and_rotates_topic(self):
        categories = ("Tecnologia", "AI", "Gaming", "Software & App")
        ordinary = [{**item(index), "category": categories[index % len(categories)]} for index in range(8)]
        ordinary.extend(({**item(50), "category": "Sicurezza"},
                         {**item(51), "title": "Come proteggere il NAS dal ransomware"}))
        recent = {**item(0, "identita-e-permessi"), "recent_ai_cyber_topic": True, "published": "2026-11-18"}
        fresh_topic = {**item(20, "protezione-dei-dati"), "published": "2026-11-17"}
        references = {**item(21, "istruzioni-e-input"), "ai_cyber_reference": True}
        chosen, reserves = selector.select_with_ai_cyber(ordinary, [recent, fresh_topic, references])
        self.assertEqual(len(chosen), 7)
        self.assertEqual(chosen[-1]["url"], fresh_topic["url"])
        self.assertEqual(sum(bool(candidate.get(ai_cyber.TOPIC_KEY)) for candidate in chosen), 1)
        self.assertIn("identita-e-permessi", {candidate.get(ai_cyber.TOPIC_KEY) for candidate in reserves})
        self.assertNotIn(recent["url"], {candidate["url"] for candidate in chosen})
        self.assertFalse({"item-50", "item-51"} & {candidate["article_id"] for candidate in [*chosen, *reserves]})

    def test_ordinary_candidate_cannot_take_a_missing_cyber_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selection.json"
            report = Path(directory) / "drafts.json"
            path.write_text(json.dumps({"items": [item(1), item(2, "protezione-dei-dati")],
                                        "reserve_items": [item(3), item(4, "istruzioni-e-input")]}))
            def generate(source, _):
                if source["article_id"] == "item-2":
                    raise generator.GeneratorFatalError("Fonte troppo corta")
                title = "Nuove misure per gli assistenti intelligenti" if source.get(ai_cyber.TOPIC_KEY) else "Aggiornamento utile per i lettori"
                return {**source, "title": title}
            with patch.object(generator, "INPUT_FILE", path), patch.object(generator, "OUTPUT_FILE", report), \
                    patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), patch.object(generator.time, "sleep"), \
                    patch.object(generator, "generate_valid_draft", side_effect=generate) as generate_mock, \
                    contextlib.redirect_stdout(io.StringIO()):
                generator.main()
            data = json.loads(report.read_text())
            self.assertEqual(data["daily_ai_cyber"], 1)
            self.assertEqual({x["article_id"] for x in data["daily_items"]}, {"item-1", "item-4"})
            self.assertNotIn("item-3", [call.args[0]["article_id"] for call in generate_mock.call_args_list])

    def test_history_skips_latest_topic_and_previously_published_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.json"
            supplemental = Path(directory) / "cyber.json"
            path.write_text(json.dumps({"items": [], "status": "empty"}))
            supplemental.write_text(json.dumps([item(1, "identita-e-permessi"),
                                                item(2, "protezione-dei-dati"),
                                                item(3, "istruzioni-e-input")]))
            used = {history.CYBER_LAST + "identita-e-permessi",
                    history.CYBER_SOURCE + "example.com/story-2",
                    history.CYBER_TOPIC + "istruzioni-e-input"}
            with patch.object(history, "INPUT_FILE", path), patch.object(history, "CYBER_CANDIDATES", supplemental), \
                    patch.dict(os.environ, {"GITHUB_TOKEN": "test", "GITHUB_REPOSITORY": "owner/repo"}), \
                    patch.object(history, "historical_reserves", return_value=[]), \
                    patch.object(history, "published_ids", return_value=used), contextlib.redirect_stdout(io.StringIO()):
                history.main()
            remaining = json.loads(path.read_text())["ai_cyber_candidates"]
            self.assertEqual([entry["article_id"] for entry in remaining], ["item-3"])
            self.assertTrue(remaining[0]["recent_ai_cyber_topic"])

    def test_slot_uses_rome_time_and_skips_already_covered_dates(self):
        rome = ZoneInfo("Europe/Rome")
        now = datetime(2026, 11, 18, 11, 17, tzinfo=rome)
        self.assertEqual(publisher.next_ai_cyber_time(set(), now).isoformat(),
                         "2026-11-18T19:30:00+01:00")
        self.assertEqual(publisher.next_ai_cyber_time({date(2026, 11, 18)}, now).isoformat(),
                         "2026-11-19T19:30:00+01:00")
        self.assertIn(date(2026, 11, 18), {when.date() for when in publisher.next_publication_times(6, now)})

    def test_wordpress_checks_public_and_future_cyber_posts(self):
        client = publisher.WordPressClient("https://example.com", "", "", False)
        client.get_or_create_term = MagicMock(side_effect=[{"id": 12}, {"id": 26}])
        client.session.get = MagicMock()
        published, scheduled = MagicMock(), MagicMock()
        published.json.return_value = [
            {"date_gmt": "2026-11-18T23:30:00", "title": {"raw": "Una notizia"}, "categories": [], "tags": [12]},
            {"date_gmt": "2026-11-18T21:00:00", "title": {"raw": "Protezione ransomware"}, "categories": [], "tags": []},
        ]
        scheduled.json.return_value = [
            {"date_gmt": "2026-11-20T08:00:00", "title": {"raw": "Una notizia"}, "categories": [26], "tags": []},
            {"date_gmt": "2026-11-21T08:00:00", "title": {"raw": "Un telefono"}, "categories": [], "tags": []},
        ]
        client.session.get.side_effect = [published, scheduled]
        self.assertEqual(client.ai_cyber_dates(datetime(2026, 11, 18, tzinfo=timezone.utc)),
                         {date(2026, 11, number) for number in (18, 19, 20)})
        self.assertEqual([call.kwargs["params"]["status"] for call in client.session.get.call_args_list],
                         ["publish", "future"])
        self.assertEqual([call.args for call in client.get_or_create_term.call_args_list],
                         [("tags", "IA e cybersicurezza"), ("categories", "Sicurezza")])


if __name__ == "__main__":
    unittest.main()
