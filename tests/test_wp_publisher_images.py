import unittest

from scripts.wp_publisher import PublisherError, featured_image_block


class FeaturedImageBlockTests(unittest.TestCase):
    def test_builds_unlinked_gutenberg_image_block(self):
        block = featured_image_block(
            {
                "id": 123,
                "source_url": "https://example.com/uploads/cover.png",
            },
            'Titolo "sicuro" & chiaro',
        )
        self.assertIn('<!-- wp:image {"id":123,"sizeSlug":"large","linkDestination":"none","style":{"border":{"width":"0px","style":"none"}}} -->', block)
        self.assertIn('src="https://example.com/uploads/cover.png"', block)
        self.assertIn('alt="Titolo &quot;sicuro&quot; &amp; chiaro"', block)
        self.assertIn('class="wp-image-123"', block)
        self.assertNotIn("<a ", block)
        self.assertIn('style="border-style:none;border-width:0px"', block)

    def test_rejects_missing_or_non_https_media(self):
        with self.assertRaises(PublisherError):
            featured_image_block({"id": 123, "source_url": "http://example.com/cover.png"}, "Titolo")
        with self.assertRaises(PublisherError):
            featured_image_block({"source_url": "https://example.com/cover.png"}, "Titolo")


if __name__ == "__main__":
    unittest.main()
