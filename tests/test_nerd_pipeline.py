import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nerd_pipeline as pipeline

class ProfileTests(unittest.TestCase):
    def setUp(self):
        for name, _, _ in pipeline.STAGES.values():
            if name in sys.modules:
                importlib.reload(sys.modules[name])

    def test_stages_use_isolated_data(self):
        for stage in pipeline.STAGES:
            mod = pipeline.configure(stage)
            for field in ('INPUT_FILE', 'OUTPUT_FILE'):
                if hasattr(mod, field):
                    self.assertEqual(getattr(mod, field).parent, pipeline.DATA)

    def test_prompt_and_classification(self):
        collector = pipeline.configure('collect')
        self.assertEqual(collector.classify_category('Titolo', '', 'Manga e fumetti'), 'Manga e fumetti')
        mod = pipeline.configure('filter')
        prompt = mod.build_prompt({'title': 'Test', 'category': 'Manga e fumetti'})
        self.assertIn('Manga e fumetti', prompt)
        self.assertNotIn('Smartphone & Mobile', prompt)
        self.assertNotIn('AI Vision', prompt)
        self.assertIn('attribuite', mod.SYSTEM_PROMPT)

    def test_publisher_blocks_unlicensed_images_and_quality_warnings(self):
        mod = pipeline.configure('publish')
        self.assertEqual(mod.image_url_from_draft({'image': 'https://example.org/image.jpg'}), '')
        self.assertEqual(mod.extract_og_image('https://example.org', None), '')
        with self.assertRaises(mod.PublisherError):
            mod.publish_one({'source_url':'https://example.org','quality_warnings':['unsupported']}, None, None, None)

    def test_live_requires_explicit_matching_target(self):
        with patch.dict('os.environ', {'WP_DRY_RUN':'false','NERD_TARGET_URL':'','WP_BASE_URL':'https://example.org'}):
            with patch.object(sys, 'argv', ['nerd_pipeline.py','publish']):
                with self.assertRaises(SystemExit):
                    pipeline.main()

    def test_selection_respects_limit_and_variety(self):
        mod = pipeline.configure('select')
        items = [{'article_id':str(i),'category':category,'story_type':'NEWS'} for i, category in enumerate(['Videogiochi']*5 + ['Manga e fumetti','Fiere ed eventi'])]
        chosen, _ = mod.select_daily(items)
        self.assertEqual(len(chosen), 5)
        self.assertEqual(len({x['category'] for x in chosen}), 3)

if __name__ == '__main__':
    unittest.main()
