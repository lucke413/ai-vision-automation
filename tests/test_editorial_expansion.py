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
        self.assertLessEqual(len(reserves), selector.RESERVE_LIMIT)

    def test_unused_slots_are_filled_with_news_when_no_practical_candidates(self):
        candidates = [item(i, cat) for i, cat in enumerate(
            ['AI', 'Sicurezza', 'Gaming', 'Software & App', 'Tecnologia',
             'PC & Hardware', 'Smartphone & Mobile', 'Streaming & Entertainment'])]
        chosen, _ = selector.select_daily(candidates)
        self.assertEqual(len(chosen), selector.DAILY_LIMIT)
        self.assertEqual(sum(x.get('editorial_kind') not in {'GUIDA', 'TUTORIAL'} for x in chosen), 6)

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
                return {**source, 'title': {'0': 'Dispositivi intelligenti per abitazioni moderne', '2': 'Accessori USB per postazioni di lavoro', '3': 'Protezione informatica contro minacce recenti'}[source['article_id']], 'quality_warnings':[], 'body_word_count':650}
            with patch.object(generator,'INPUT_FILE',inp), patch.object(generator,'OUTPUT_FILE',out), patch.dict('os.environ',{'GEMINI_API_KEY':'test-not-a-real-key'}), patch.object(generator,'generate_valid_draft',side_effect=draft), patch.object(generator.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
                generator.main()
            result=json.loads(out.read_text())
            daily=[x for x in result['items'] if x['publication_slot']=='today']
            self.assertEqual({x['category'] for x in daily}, {'Casa smart','Sicurezza'})

    def test_quality_mode_six_posts_with_quality_gates(self):
        from zoneinfo import ZoneInfo
        self.assertEqual(selector.DAILY_LIMIT, 6)
        self.assertEqual(generator.DAILY_LIMIT, 6)
        self.assertEqual(generator.MAX_ITEMS, 6 + generator.RESERVE_LIMIT)
        self.assertEqual(selector.RESERVE_LIMIT, generator.RESERVE_LIMIT)
        self.assertEqual(selector.MAX_NEWS_PER_DAY, 3)
        self.assertEqual(selector.MAX_GUIDES_PER_DAY, 2)
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

    def test_guide_word_bozza_is_not_an_unsupported_claim(self):
        example = "Prepara una bozza di email e controlla il destinatario."
        generator.validate_editorial_body(example)
        self.assertFalse(any(p.search(example) for p in publisher.PUBLIC_FORBIDDEN_PATTERNS))
        with self.assertRaises(generator.GeneratorFatalError):
            generator.validate_editorial_body("Abbiamo provato questo strumento per voi.")

    def test_body_only_repair_keeps_original_metadata(self):
        source = {
            "article_id": "fixed-id", "title": "Esempio guida email per principianti",
            "description": " ".join(["Guida pratica originale"] * 70),
            "url": "https://chatgpt.com/", "editorial_kind": "GUIDA",
            "topic_slug": "email-esempio"
        }
        original = {
            "title": "Come preparare una email chiara usando l'AI",
            "excerpt": "Come organizzare una richiesta utile.",
            "body_markdown": " ".join(["testo"] * 410),
            "seo_title": "Email con AI", "seo_description": "Come preparare email",
            "slug": "email-esempio", "tags": ["AI"],
            "fact_check_notes": []
        }
        repaired = {"body_markdown": " ".join(["passaggio"] * 675)}
        with patch.object(generator, "enrich_source", side_effect=lambda x: x), patch.object(
            generator, "call_gemini", side_effect=[original, repaired]
        ) as call:
            draft = generator.generate_valid_draft(source, "fake-key")
        self.assertEqual(draft["body_word_count"], 675)
        self.assertEqual(draft["slug"], original["slug"])
        self.assertEqual(draft["title"], original["title"])
        self.assertEqual(call.call_count, 2)
        self.assertIn("SOLO con JSON", call.call_args.args[0])

    def test_invalid_repair_still_fails_quality_gate(self):
        source = {
            "article_id": "fixed-id", "title": "Guida con fonte sufficiente",
            "description": " ".join(["Metodo pratico affidabile"] * 70),
            "url": "https://chatgpt.com/", "editorial_kind": "GUIDA",
            "topic_slug": "guida-prova"
        }
        raw = {
            "title": "Come organizzare contenuti con una guida utile",
            "excerpt": "Esempio", "body_markdown": " ".join(["testo"] * 420),
            "seo_title": "Guida", "seo_description": "Passaggi",
            "slug": "guida-prova", "tags": ["AI"], "fact_check_notes": []
        }
        with patch.object(generator, "enrich_source", side_effect=lambda x: x), patch.object(
            generator, "call_gemini",
            side_effect=[raw, {"body_markdown": " ".join(["breve"] * 430)},
                         {"body_markdown": " ".join(["corto"] * 440)}]
        ):
            with self.assertRaises(generator.GeneratorFatalError):
                generator.generate_valid_draft(source, "fake-key")

    def test_reserves_prefer_noncommercial_news(self):
        candidates = [
            {**item(0, "Gaming", "NEWS"), "final_score": 110},
            {**item(1, "Offerte & Prezzi", "OFFERTA"), "final_score": 105},
        ]
        candidates.extend(
            {**item(10+i, "Offerte & Prezzi", "OFFERTA"), "final_score": 100-i}
            for i in range(8)
        )
        candidates.extend(
            {**item(30+i, "Sicurezza", "NEWS"), "final_score": 70-i}
            for i in range(8)
        )
        chosen, reserves = selector.select_daily(candidates)
        self.assertEqual(len(reserves), 6)
        self.assertTrue(all(not selector.is_offer(x) for x in reserves))
        self.assertEqual(sum(selector.is_offer(x) for x in chosen), 1)

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
        draft={**item(0,'Casa smart','GUIDA'), 'body_markdown':' '.join(['parola']*510)}
        with patch.object(publisher,'fallback_png',return_value=b'png'):
            publisher.publish_one(draft,datetime.now(timezone.utc),client,None)
        self.assertEqual(client.create_post.call_args.args[0]['categories'],[1,2])
        self.assertEqual(publisher.category_for(item(1,'Gaming')), 'Gaming e console')
        self.assertEqual(publisher.category_for(item(2,'Casa smart','OFFERTA')), 'Offerte')

    def test_source_parser_entry_content_without_page_navigation(self):
        parser = generator.SourceArticleParser()
        parser.feed('<div class="entry-content"><h2>Titolo</h2><p>Fatti attendibili.</p>'
                    '<nav>Menu da escludere</nav><script>no_script()</script>'
                    '<p>Ulteriori informazioni.</p></div>')
        result = parser.text()
        self.assertIn("Fatti attendibili", result)
        self.assertIn("Ulteriori informazioni", result)
        self.assertNotIn("Menu da escludere", result)
        self.assertNotIn("no_script", result)

    def test_existing_wordpress_post_does_not_upload_images(self):
        client = MagicMock()
        client.dry_run = False
        client.existing_post.return_value = {"id": 88, "link": "https://example.com/post",
                                             "status": "future"}
        draft = {**item(12, "AI"), "body_markdown": " ".join(["fatto"] * 520),
                 "slug": "articolo-esistente"}
        result = publisher.publish_one(draft, datetime.now(timezone.utc), client, None)
        self.assertEqual(result["status"], "already_exists")
        client.upload_media.assert_not_called()
        client.create_post.assert_not_called()

    def test_wordpress_term_conflict_refetch_returns_single_term(self):
        client = publisher.WordPressClient(
            "https://example.com", "", "", dry_run=False
        )
        first_lookup = MagicMock()
        first_lookup.json.return_value = []
        conflict = MagicMock()
        conflict.status_code = 400
        refetch = MagicMock()
        refetch.json.return_value = [
            {"id": 17, "name": "Tecnologia e prodotti", "slug": "tecnologia-e-prodotti"}
        ]
        client.session.get = MagicMock(side_effect=[first_lookup, refetch])
        client.session.post = MagicMock(return_value=conflict)

        term = client.get_or_create_term("categories", "Tecnologia e prodotti")

        self.assertEqual(term["id"], 17)
        self.assertEqual(term["name"], "Tecnologia e prodotti")
        self.assertIsInstance(term, dict)
        self.assertEqual(term.get("id"), 17)

