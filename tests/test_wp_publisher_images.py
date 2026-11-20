import io
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

from scripts.cover_media import (COVER_SIZE, CoverCredit, commons_photos, cover_exposure, grade_ai_cover,
                                 is_interim_card, is_striped_cover)

from scripts.wp_publisher import PublisherError, download_cover_photo, download_image, featured_image_block, select_cover


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
        image = Image.new("RGB", (1200, 675), (46, 55, 96))
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

    def test_recognizes_the_repeated_interim_card(self):
        image = Image.new("RGB", (1200, 675), "#251933")
        self.assertFalse(is_interim_card(image))
        ImageDraw.Draw(image).rounded_rectangle((72, 148, 136, 156), radius=4, fill="#f6af66")
        self.assertTrue(is_interim_card(image))

    def test_download_checks_actual_file_and_rejects_striped_cover(self):
        session = MagicMock()
        response = session.get.return_value.__enter__.return_value
        output = io.BytesIO()
        self.retired_cover().save(output, "PNG")
        response.iter_content.return_value = [output.getvalue()]
        self.assertIsNone(download_image("https://example.com/image.png", session))
        response.iter_content.return_value = [b"<html>Errore</html>"]
        self.assertIsNone(download_image("https://example.com/image.png", session))
        output = io.BytesIO()
        Image.new("RGB", (640, 360), "#df314a").save(output, "PNG")
        response.iter_content.return_value = [output.getvalue()]
        self.assertEqual(download_image("https://example.com/image.jpg", session)[1], ".png")

    def test_lifts_a_dark_scene_and_rejects_flat_pixels(self):
        scene = Image.linear_gradient("L").resize(COVER_SIZE).point(lambda level: 18 + level * 65 // 255)
        self.assertTrue(cover_exposure(scene).dark)
        self.assertTrue(cover_exposure(grade_ai_cover(scene)).usable)
        self.assertFalse(cover_exposure(Image.new("RGB", COVER_SIZE, "gray")).usable)

class CoverSelectionTests(unittest.TestCase):
    def setUp(self):
        self.draft = {
            "title": "Notizie su Robert Pattinson", "cover_subject": "Robert Pattinson",
            "source_image_url": "https://example.com/source.jpg",
            "cover_prompt": "Indie film camera in a painted studio",
        }
        self.session = MagicMock()

    @patch("scripts.wp_publisher.generate_ai_cover", return_value=b"ai")
    def test_unlicensed_rss_image_is_never_downloaded(self, generate):
        self.session.get.return_value.json.return_value = {}
        selected = select_cover(self.draft, self.session)
        self.assertEqual(selected[:4], (b"ai", ".jpg", "ai_generated", ""))
        self.assertEqual(self.session.get.call_args.args[0], "https://commons.wikimedia.org/w/api.php")
        generate.assert_called_once_with(self.draft)

    @patch("scripts.wp_publisher.generate_ai_cover")
    @patch("scripts.wp_publisher.download_cover_photo", return_value=b"photo")
    def test_approved_source_precedes_generation(self, download, generate):
        self.draft.update(image_rights_status="owned", image_license="Copyright AI Vision")
        self.assertEqual(select_cover(self.draft, self.session)[:4],
                         (b"photo", ".jpg", "licensed_source_image", self.draft["source_image_url"]))
        download.assert_called_once_with(self.draft["source_image_url"], self.session)
        generate.assert_not_called()

    def test_commons_checks_license_and_relevance(self):
        metadata = {
            "Artist": {"value": "<span>Harald Krichel</span>"},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-nc/4.0/"},
            "LicenseShortName": {"value": "CC BY 4.0"},
        }
        image = {
            "width": 1200, "height": 800, "extmetadata": metadata,
            "thumburl": "https://upload.wikimedia.org/wikipedia/commons/r.jpg",
        }
        photo = {"title": "File:Robert Pattinson in Berlin.jpg", "imageinfo": [image]}
        self.session.get.return_value.json.return_value = {"query": {"pages": [photo]}}
        args = ("", "Robert Pattinson", self.draft["title"], self.session)
        self.assertEqual(list(commons_photos(*args)), [])
        metadata["LicenseUrl"]["value"] = "https://creativecommons.org/licenses/by/4.0/"
        url, credit = next(commons_photos(*args))
        self.assertEqual(url, image["thumburl"])
        self.assertIn("Harald Krichel", credit.markup())
        self.assertIn("https://creativecommons.org/licenses/by/4.0/", credit.markup())
        photo["title"] = "File:Another person.jpg"
        self.assertEqual(list(commons_photos(*args)), [])

    @patch("scripts.wp_publisher.download_cover_photo", side_effect=[None, b"second photo"])
    @patch("scripts.wp_publisher.commons_photos")
    def test_tries_the_next_verified_photo_when_one_is_unusable(self, candidates, download):
        credit = CoverCredit("Foto: autore")
        candidates.return_value = iter([("https://example.com/one.jpg", credit),
                                        ("https://example.com/two.jpg", credit)])
        selected = select_cover(self.draft, self.session)
        self.assertEqual(selected, (b"second photo", ".jpg", "wikimedia_commons", "https://example.com/two.jpg", credit))
        self.assertEqual(download.call_count, 2)

    @patch("scripts.wp_publisher.download_image")
    def test_rejects_small_or_transparent_pictures_as_cover_photos(self, download):
        for image in (Image.new("RGB", (640, 360)), Image.new("RGBA", COVER_SIZE, (220, 150, 140, 0))):
            stream = io.BytesIO()
            image.save(stream, "PNG")
            download.return_value = (stream.getvalue(), ".png")
            self.assertIsNone(download_cover_photo("https://example.com/photo.png", self.session))

    def test_non_https_credit_url_cannot_be_injected(self):
        markup = CoverCredit("<credit>", "javascript:alert(1)").markup()
        self.assertEqual(markup, "&lt;credit&gt;")


if __name__ == "__main__":
    unittest.main()
