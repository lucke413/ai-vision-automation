import unittest

from scripts.inline_image_repair import needs_inline_cover, normalize_leading_cover


class InlineImageRepairTests(unittest.TestCase):
    def test_post_without_inline_image_is_targeted(self):
        self.assertTrue(needs_inline_cover({
            "featured_media": 42,
            "content": {"raw": "<p>Testo dell'articolo</p>"},
        }))

    def test_image_inside_body_does_not_replace_leading_cover(self):
        self.assertTrue(needs_inline_cover({
            "featured_media": 42,
            "content": {"raw": '<h2>Introduzione</h2><p>Testo</p><figure><img src="https://example.com/body.png"></figure>'},
        }))

    def test_borderless_leading_image_is_not_targeted(self):
        self.assertFalse(needs_inline_cover({
            "featured_media": 42,
            "content": {"raw": '<!-- wp:image {"id":42,"style":{"border":{"width":"0px","style":"none"}}} --><figure class="wp-block-image has-custom-border"><img src="https://example.com/cover.png" style="border-style:none;border-width:0px" /></figure><!-- /wp:image -->'},
        }))

    def test_leading_image_without_border_reset_is_targeted(self):
        self.assertTrue(needs_inline_cover({
            "featured_media": 42,
            "content": {"raw": '<figure><img src="https://example.com/cover.png"></figure>'},
        }))

    def test_normalizer_removes_border_from_leading_image(self):
        value = '<!-- wp:image {"id":42} --><figure class="wp-block-image"><img src="https://example.com/cover.png" /></figure><!-- /wp:image -->'
        normalized = normalize_leading_cover(value)
        self.assertIn('"width":"0px","style":"none"', normalized)
        self.assertIn('style="border-style:none;border-width:0px"', normalized)

    def test_post_without_featured_media_is_not_targeted(self):
        self.assertFalse(needs_inline_cover({
            "featured_media": 0,
            "content": {"raw": "<p>Testo</p>"},
        }))

    def test_gutenberg_marker_without_actual_image_is_targeted(self):
        self.assertTrue(needs_inline_cover({
            "featured_media": 42,
            "content": {"raw": '<!-- wp:image {"id":42} -->'},
        }))


if __name__ == "__main__":
    unittest.main()
