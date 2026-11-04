import unittest
from scripts.site_public_fixes import clean_social, fix_post, widget_change, OLD, NEW

HTML = '<div>Seguici sui social <a href="https://t.me/aivision_tech">Telegram</a></div>'


class PublicFixTests(unittest.TestCase):
    def test_fences_only(self):
        self.assertEqual(clean_social('```html\n' + HTML + '\n```'), HTML)
        self.assertEqual(clean_social(HTML), HTML)

    def test_unrelated_or_nested_code_is_untouched(self):
        for value in ('```html\n<p>Example</p>\n```', 'intro\n```html\n'+HTML+'\n```', '```html\n'+HTML+'```\n```'):
            self.assertEqual(clean_social(value), value)

    def test_widget_preserves_other_settings(self):
        row = widget_change({'id': 'custom_html-2', 'id_base': 'custom_html',
                             'instance': {'raw': {'content': '```html\n'+HTML+'\n```', 'title': 'Social'}}})
        self.assertEqual(row['after']['title'], 'Social')
        self.assertEqual(row['before']['content'], '```html\n'+HTML+'\n```')
        self.assertEqual(row['after']['content'], HTML)

    def test_date_fix_is_narrow_and_idempotent(self):
        before = '<p>19 novembre. Preload ' + OLD + '.</p>'
        after = '<p>19 novembre. Preload ' + NEW + '.</p>'
        self.assertEqual(fix_post(before), after)
        self.assertEqual(fix_post(after), after)
        self.assertEqual(fix_post(OLD), OLD)
        self.assertEqual(fix_post(before+before), before+before)
