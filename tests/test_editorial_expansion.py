import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import rss_collector as collector
import ai_filter
import article_generator as generator
import daily_selector as selector
import wp_publisher as publisher


def item(n, category, story_type='NEWS'):
    return dict(article_id=str(n), title=f'Articolo {n}', category=category,
                story_type=story_type, final_score=100-n)

class EditorialExpansionTests(unittest.TestCase):
    def test_specific_topics_and_existing_topics(self):
        examples = [('Robot aspirapolvere: novità per la casa', 'Casa smart'),
                    ('Hub USB-C: quali porte scegliere', 'Accessori e postazioni'),
                    ('PS5: aggiornamento PlayStation', 'Gaming'),
                    ('ChatGPT OpenAI: nuovo modello', 'AI'),
                    ('Malware e phishing: sicurezza informatica', 'Sicurezza')]
        for title, expected in examples:
            self.assertEqual(collector.classify_category(title, '', 'tech'), expected)

    def test_categories_consistent(self):
        for name in selector.EXPANSION_CATEGORIES:
            self.assertIn(name, collector.CATEGORY_KEYWORDS)
            self.assertIn(name, ai_filter.VALID_CATEGORIES)
            self.assertIn(name, ai_filter.build_prompt({}))
            self.assertIn(name, generator.VALID_CATEGORIES)
            self.assertIn(name, publisher.MACRO_CATEGORIES)

    def test_new_topics_cannot_displace_daily_mix(self):
        candidates = [item(i, cat) for i, cat in enumerate(
            ['Casa smart']*4 + ['Accessori e postazioni']*4 + ['AI','Sicurezza','Gaming','Software & App','Tecnologia'])]
        chosen, reserves = selector.select_daily(candidates)
        self.assertEqual(len(chosen), 6)
        self.assertEqual(sum(x['category'] in selector.EXPANSION_CATEGORIES for x in chosen), 1)
        self.assertIn('AI', {x['category'] for x in chosen})
        self.assertLessEqual(len(reserves), 3)

    def test_no_forced_new_topic_and_one_offer(self):
        candidates = [item(i, cat, 'OFFERTA' if i < 2 else 'NEWS') for i, cat in enumerate(
            ['Offerte & Prezzi','Offerte & Prezzi','AI','Sicurezza','Gaming','Software & App','Tecnologia'])]
        chosen, _ = selector.select_daily(candidates)
        self.assertEqual(len(chosen), 6)
        self.assertEqual(sum(selector.is_offer(x) for x in chosen), 1)

    def test_reserve_promotion_preserves_topic_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            inp=Path(directory)/'in.json';out=Path(directory)/'out.json'
            inp.write_text(json.dumps({'items':[item(0,'Casa smart'),item(1,'AI')],
                                      'reserve_items':[item(2,'Accessori e postazioni'),item(3,'Sicurezza')]}))
            def draft(source, key):
                if source['article_id']=='1':
                    raise generator.GeneratorFatalError('Simulated rejection')
                return {**source,'quality_warnings':[], 'body_word_count':650}
            with patch.object(generator,'INPUT_FILE',inp), patch.object(generator,'OUTPUT_FILE',out), patch.dict('os.environ',{'GEMINI_API_KEY':'test-not-a-real-key'}), patch.object(generator,'generate_valid_draft',side_effect=draft), patch.object(generator.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
                generator.main()
            result=json.loads(out.read_text())
            daily=[x for x in result['items'] if x['publication_slot']=='today']
            self.assertEqual({x['category'] for x in daily}, {'Casa smart','Sicurezza'})

    def test_six_posts_and_new_slot_at_1830(self):
        from zoneinfo import ZoneInfo
        self.assertEqual(selector.DAILY_LIMIT, 6)
        self.assertEqual(generator.DAILY_LIMIT, 6)
        self.assertEqual(generator.MAX_ITEMS, 6 + generator.RESERVE_LIMIT)
        with patch.dict('os.environ', {'WP_TIMEZONE': 'Europe/Rome'}, clear=True):
            self.assertEqual(
                [value.strftime('%H:%M') for value in publisher.parse_slot_times()],
                ['08:00', '10:30', '14:00', '16:30', '18:30', '20:30']
            )
            now = datetime(2026, 10, 16, 11, 17, tzinfo=ZoneInfo('Europe/Rome'))
            planned = publisher.next_publication_times(6, now=now)
            self.assertEqual(
                [value.strftime('%Y-%m-%d %H:%M') for value in planned],
                [
                    '2026-10-16 14:00', '2026-10-16 16:30',
                    '2026-10-16 18:30', '2026-10-16 20:30',
                    '2026-10-17 08:00', '2026-10-17 10:30'
                ]
            )

    def test_rejects_misleading_first_hand_review_title(self):
        with self.assertRaises(generator.GeneratorFatalError):
            generator.validate_editorial_title("Sony WH-CH730N in prova: la nostra recensione")
        generator.validate_editorial_title("Sony WH-CH730N: caratteristiche e analisi delle informazioni disponibili")

    def test_rejects_first_hand_experience_claims(self):
        with self.assertRaises(generator.GeneratorFatalError):
            generator.validate_editorial_body("Durante il nostro ascolto abbiamo notato bassi molto presenti.")

    def test_evidence_gate_counts_source_material(self):
        weak = {"title": "Titolo breve", "description": "pochi dati", "source_text": ""}
        rich = {"title": "Titolo", "description": " ".join(["dato"] * 150), "source_text": ""}
        self.assertLess(generator.evidence_word_count(weak), generator.MIN_EVIDENCE_WORDS)
        self.assertGreaterEqual(generator.evidence_word_count(rich), generator.MIN_EVIDENCE_WORDS)

    def test_guide_keeps_format_and_adds_topic(self):
        client=MagicMock();client.dry_run=True
        client.get_or_create_term.side_effect=lambda kind,name: {'id':{'Guide':1,'Casa smart':2}[name]}
        client.related_link.return_value='';client.existing_post.return_value=None
        client.upload_media.return_value={'id':0};client.create_post.return_value={'id':123}
        draft={**item(0,'Casa smart','GUIDA'), 'body_markdown':' '.join(['parola']*410)}
        with patch.object(publisher,'fallback_png',return_value=b'png'):
            publisher.publish_one(draft,datetime.now(timezone.utc),client,None)
        self.assertEqual(client.create_post.call_args.args[0]['categories'],[1,2])
        self.assertEqual(publisher.category_for(item(1,'Gaming')), 'Gaming e console')
        self.assertEqual(publisher.category_for(item(2,'Casa smart','OFFERTA')), 'Offerte')


    def test_practical_guides_have_unique_sources(self):
        import practical_guides
        self.assertGreaterEqual(len(practical_guides.TOPICS), 20)
        result = practical_guides.inject(
            {"status": "ok", "items": []},
            "2026-10-17", lambda slug: False,
        )
        self.assertEqual(result["practical_guide_candidates"], 6)
        self.assertEqual(len({c["article_id"] for c in result["items"]}), 6)
        self.assertEqual(sum(x["editorial_kind"] == "GUIDA" for x in result["items"]), 4)
        self.assertEqual(sum(x["editorial_kind"] == "TUTORIAL" for x in result["items"]), 2)
        for candidate in result["items"]:
            self.assertGreaterEqual(generator.evidence_word_count(candidate), 140)
            self.assertIn("GUIDA DIDATTICA ORIGINALE", generator.build_prompt(candidate))
            self.assertEqual(generator.enrich_source(candidate)["source_text"], candidate["source_text"])

    def test_practical_guides_are_not_reused_when_existing(self):
        import practical_guides
        used = {x[0] for x in practical_guides.TOPICS}
        result = practical_guides.inject(
            {"status": "ok", "items": []},
            "2026-10-17", lambda slug: slug in used,
        )
        self.assertEqual(result["items"], [])

    def test_balanced_news_guides_and_tutorials(self):
        import practical_guides
        news = [{**item(i, cat), "url": "https://example.com/article-" + str(i)}
                for i, cat in enumerate(["AI", "Gaming", "Sicurezza", "Software & App", "Tecnologia", "PC & Hardware"])]
        guide_items = [practical_guides.make_candidate(x) for x in practical_guides.TOPICS]
        candidates = selector.valid_candidates({"status": "ok", "items": news + guide_items})
        chosen, reserves = selector.select_daily(candidates)
        self.assertEqual(len(chosen), 6)
        self.assertEqual(sum(x.get("editorial_kind") == "GUIDA" for x in chosen), 2)
        self.assertEqual(sum(x.get("editorial_kind") == "TUTORIAL" for x in chosen), 1)
        self.assertEqual(sum(not x.get("editorial_kind") for x in chosen), 3)

    def test_practical_guides_have_links_lists_and_original_diagrams(self):
        import practical_guides
        draft = practical_guides.make_candidate(practical_guides.TOPICS[0])
        self.assertIn("<ol>", publisher.markdown_to_html("## Procedura\n\n1. Prepara i dati\n2. Controlla il risultato"))
        self.assertIn("Prova lo strumento", publisher.guide_resources(draft))
        self.assertTrue(publisher.guide_infographic(draft).startswith(b"\x89PNG\r\n\x1a\n"))



    def test_practical_prompts_and_illustrations_are_guide_only(self):
        import practical_guides
        sample = practical_guides.make_candidate(practical_guides.TOPICS[0])
        self.assertTrue(sample["example_prompt"])
        self.assertTrue(sample["advanced_prompt"])
        self.assertIn("[", sample["advanced_prompt"])
        self.assertIn("chatgpt.com", sample["official_links"][0]["url"])
        self.assertNotIn("help.openai.com/en", publisher.guide_resources(sample))
        html = publisher.guide_prompt_blocks(sample)
        self.assertIn("Prompt semplice da copiare", html)
        self.assertIn("Prompt avanzato", html)
        self.assertIn("<pre", html)
        self.assertTrue(publisher.guide_inline_diagram(sample, "prompt").startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertTrue(publisher.guide_inline_diagram(sample, "check").startswith(b"\x89PNG\r\n\x1a\n"))
        standard_news = {"title": "Notizia tech", "category": "Tecnologia", "story_type": "NEWS"}
        self.assertEqual(publisher.guide_prompt_blocks(standard_news), "")
        self.assertEqual(publisher.guide_resources(standard_news), "")
        client = MagicMock()
        self.assertEqual(publisher.guide_inline_figures(standard_news, client, "news"), [])
        client.upload_media.assert_not_called()


    def test_practical_guides_use_real_beginner_urls(self):
        import practical_guides
        for topic in practical_guides.TOPICS:
            item = practical_guides.make_candidate(topic)
            self.assertNotIn("/en/articles/", item["url"])
            self.assertNotIn("/en/articles/", item["official_links"][0]["url"])
            self.assertIn("visual_demo", item)
            self.assertEqual(len(item["visual_demo"]["lines"]), 3)
        examples = [practical_guides.make_candidate(topic) for topic in practical_guides.TOPICS]
        maths = next(x for x in examples if "matematica" in x["topic_slug"])
        self.assertIn("3x", maths["visual_demo"]["heading"])

    def test_practical_images_must_be_uploaded_and_in_article(self):
        import practical_guides
        draft = practical_guides.make_candidate(practical_guides.TOPICS[0])
        client = MagicMock()
        client.dry_run = False
        client.upload_media.side_effect = [
            {"id": 9, "source_url": "https://example.com/a.png"},
            {"id": 10, "source_url": "https://example.com/b.png"},
        ]
        figures = publisher.guide_inline_figures(draft, client, "sample")
        self.assertEqual(len(figures), 2)
        self.assertIn("a.png", figures[0])
        self.assertIn("b.png", figures[1])
        body = publisher.markdown_to_html(
            "## Procedura pratica\n\n1. Prepara i dati\n2. Prova il prompt\n\n"
            "## Verifica del risultato\n\nControlla la risposta."
        )
        enriched = publisher.guide_place_figures(body, figures)
        self.assertLess(enriched.index("a.png"), enriched.index("Verifica del risultato"))
        self.assertLess(enriched.index("b.png"), enriched.index("Verifica del risultato"))
        self.assertEqual(client.upload_media.call_count, 2)

    def test_practical_images_fail_closed_on_bad_upload(self):
        import practical_guides
        draft = practical_guides.make_candidate(practical_guides.TOPICS[0])
        client = MagicMock()
        client.dry_run = False
        client.upload_media.return_value = {"id": None, "source_url": ""}
        with self.assertRaises(publisher.PublisherError):
            publisher.guide_inline_figures(draft, client, "sample")



    def test_guide_overflow_cannot_fill_news_slots(self):
        import practical_guides
        news = [{**item(i, cat), "url": f"https://example.com/n-{i}"}
                for i, cat in enumerate(["AI", "Gaming", "Sicurezza"])]
        practical = [practical_guides.make_candidate(t) for t in practical_guides.TOPICS]
        candidates = selector.valid_candidates({"status": "ok", "items": news + practical})
        chosen, reserves = selector.select_daily(candidates)
        self.assertEqual(len(chosen), 6)
        self.assertEqual(sum(bool(x.get("editorial_kind")) for x in chosen), 3)
        self.assertTrue(all(not x.get("editorial_kind") for x in reserves))
        chosen_without_news, reserves_without_news = selector.select_daily(
            selector.valid_candidates({"status": "ok", "items": practical})
        )
        self.assertEqual(len(chosen_without_news), 3)
        self.assertEqual(reserves_without_news, [])

    def test_failed_news_is_not_replaced_with_additional_guides(self):
        import practical_guides
        with tempfile.TemporaryDirectory() as folder:
            inp, out = Path(folder)/"selection.json", Path(folder)/"drafts.json"
            practical = [practical_guides.make_candidate(t) for t in practical_guides.TOPICS]
            guide = next(x for x in practical if x["editorial_kind"] == "GUIDA")
            tutorial = next(x for x in practical if x["editorial_kind"] == "TUTORIAL")
            news = item(1, "Gaming")
            extra_guide = next(x for x in practical if x["editorial_kind"] == "GUIDA" and x["article_id"] != guide["article_id"])
            inp.write_text(json.dumps({
                "items": [{**guide, "publication_slot": "today"},
                          {**tutorial, "publication_slot": "today"}, news],
                "reserve_items": [extra_guide],
            }))
            def mock_generate(source, _key):
                if not source.get("editorial_kind"):
                    raise generator.GeneratorFatalError("notizia non verificabile")
                return {**source, "publication_slot": source["publication_slot"],
                        "body_word_count": 650, "quality_warnings": []}
            with patch.object(generator, "INPUT_FILE", inp), patch.object(generator, "OUTPUT_FILE", out), patch.dict("os.environ", {"GEMINI_API_KEY":"test"}), patch.object(generator, "generate_valid_draft", side_effect=mock_generate), patch.object(generator.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
                generator.main()
            output = json.loads(out.read_text())
            self.assertEqual(output["daily_generated"], 2)
            self.assertEqual(sum(x["publication_slot"] == "today" for x in output["items"]), 2)

if __name__=='__main__': unittest.main()
