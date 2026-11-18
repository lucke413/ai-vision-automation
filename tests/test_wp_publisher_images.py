import io
import unittest
from unittest.mock import MagicMock

from PIL import Image

from scripts.editorial_cover import COVER_SIZE, editorial_cover, is_striped_cover

from scripts.wp_publisher import PublisherError, download_image, featured_image_block


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


class EditorialCoverTests(unittest.TestCase):
    @staticmethod
    def retired_cover():
        image = Image.new("RGB", COVER_SIZE, (46, 55, 96))
        pixels = image.load()
        for y in range(image.height):
            for x in range(image.width):
                diagonal = ((x + y) // 90) % 2 == 0
                band = (x // 160) % 3 == 0 and 90 < y < 585
                pixels[x, y] = (46 + 22 * diagonal, 55 + 14 * diagonal, 96 + 28 * band)
        return image

    def test_recognizes_old_cover_after_wordpress_resize(self):
        old = self.retired_cover()
        self.assertTrue(is_striped_cover(old))
        output = io.BytesIO()
        old.resize((320, 180)).save(output, format="JPEG", quality=70)
        self.assertTrue(is_striped_cover(Image.open(io.BytesIO(output.getvalue()))))

    def test_illustration_is_specific_to_the_article(self):
        first = editorial_cover("Prezzi Netflix in Italia", "Tecnologia e prodotti")
        other = editorial_cover("Xiaomi 18 Pro in Italia", "Tecnologia e prodotti")
        self.assertNotEqual(first, other)
        with Image.open(io.BytesIO(first)) as image:
            self.assertEqual(image.size, COVER_SIZE)
            self.assertFalse(is_striped_cover(image))

    def test_download_checks_actual_file_and_rejects_striped_cover(self):
        session = MagicMock()
        response = session.get.return_value.__enter__.return_value
        output = io.BytesIO()
        self.retired_cover().save(output, "PNG")
        response.iter_content.return_value = [output.getvalue()]
        self.assertIsNone(download_image("https://example.com/image.png", session))
        response.iter_content.return_value = [b"<html>Errore</html>"]
        self.assertIsNone(download_image("https://example.com/image.png", session))
        response.iter_content.return_value = [editorial_cover("GTA 6", "Gaming e console")]
        self.assertEqual(download_image("https://example.com/image.jpg", session)[1], ".png")


if __name__ == "__main__":
    unittest.main()
