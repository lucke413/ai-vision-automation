import unittest

from scripts.inline_image_repair import needs_inline_cover


class InlineImageRepairTests(unittest.TestCase):
    def test_post_with_featured_media_and_no_inline_image_is_targeted(self):
        self.assertTrue(needs_inline_cover({
            "featured_media": 42,
            "content": {"raw": "<p>Testo dell'articolo</p>"},
        }))

    def test_post_with_inline_image_is_not_targeted(self):
        self.assertFalse(needs_inline_cover({
            "featured_media": 42,
            "content": {"raw": '<figure><img src="https://example.com/cover.png"></figure>'},
        }))

    def test_post_without_featured_media_is_not_targeted(self):
        self.assertFalse(needs_inline_cover({
            "featured_media": 0,
            "content": {"raw": "<p>Testo</p>"},
        }))

    def test_gutenberg_image_marker_is_not_duplicated(self):
        self.assertFalse(needs_inline_cover({
            "featured_media": 42,
            "content": {"raw": '<!-- wp:image {"id":42} -->'},
        }))


if __name__ == "__main__":
    unittest.main()
