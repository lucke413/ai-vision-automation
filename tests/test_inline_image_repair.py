import io
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from scripts import inline_image_repair as repair
from scripts import cover_quality_repair as quality


class InlineImageRepairTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.base_url = "https://example.com"
        self.client._url.side_effect = lambda resource: f"https://example.com/wp-json/wp/v2/{resource}"
        self.old_url = "https://example.com/wp-content/uploads/old.png"
        self.new_url = "https://example.com/wp-content/uploads/ai-vision-cover-1.png"
        self.media = {"id": 42, "source_url": self.old_url}
        self.body = "<p>Testo originale.</p>\n<figure><img src='detail.png'></figure>"
        self.cover = repair.featured_image_block(self.media, "Titolo")

    def post(self, content, featured=True):
        return {
            "id": 1, "status": "future", "featured_media": 42 if featured else 0,
            "title": {"raw": "Titolo"}, "content": {"raw": content},
            "_embedded": {"wp:featuredmedia": [self.media]} if featured else {},
        }

    @patch.object(repair, "image_state", return_value="ok")
    def test_healthy_post_is_untouched(self, state):
        self.assertIsNone(repair.repair_post(self.client, self.post(self.cover + self.body)))
        self.client.session.post.assert_not_called()
        state.assert_called_once()

    @patch.object(repair, "image_state", side_effect=lambda url, *args: "ok" if url else "missing")
    def test_missing_inline_cover_reuses_featured_media(self, _):
        plan = repair.plan_repair(self.client, self.post(self.body))
        self.assertEqual(plan.media, self.media)
        self.assertEqual(plan.inline_state, "missing")

    @patch.object(repair, "image_state", return_value="missing")
    def test_post_without_images_gets_an_original_cover(self, _):
        plan = repair.plan_repair(self.client, self.post(self.body, featured=False))
        self.assertEqual(plan.media, {})
        self.assertIsNone(plan.replace_span)

    @patch.object(repair, "image_state", side_effect=lambda url, *args: "ok" if url else "missing")
    def test_existing_leading_photo_can_restore_missing_featured_media(self, _):
        with patch.object(repair, "fetch_media", return_value=self.media):
            result = repair.plan_repair(self.client, self.post(self.cover + self.body, featured=False))
        self.assertEqual(result.media, self.media)
        self.assertIsNone(result.replace_span)

    @patch.object(repair, "image_state", return_value="striped")
    @patch.object(repair, "request_with_retry")
    @patch.object(repair, "generate_ai_cover")
    def test_replaces_both_covers_without_touching_body_or_schedule(self, generate, request, _):
        output = io.BytesIO()
        Image.new("RGB", (1200, 675), "red").save(output, "JPEG")
        generate.return_value = output.getvalue()
        post = self.post(self.cover + self.body)
        new_media = {"id": 77, "source_url": self.new_url}
        self.client.upload_media.return_value = new_media
        response = MagicMock()
        saved = MagicMock()
        saved.json.return_value = {
            "status": "future", "featured_media": 77,
            "content": {"raw": repair.featured_image_block(new_media, "Titolo", repair.CoverCredit("")) + "\n\n" + self.body},
        }
        current = MagicMock()
        current.json.return_value = post
        empty = MagicMock()
        empty.json.return_value = []
        request.side_effect = [current, empty, response, saved]
        result = repair.repair_post(self.client, post)
        payload = request.call_args_list[2].kwargs["json"]
        self.assertEqual(set(payload), {"content", "featured_media", "meta"})
        self.assertEqual(payload["featured_media"], 77)
        self.assertIn(self.new_url, payload["content"])
        self.assertNotIn(self.old_url, payload["content"])
        self.assertTrue(payload["content"].endswith(self.body))
        self.assertEqual(result["status"], "future")
        self.assertNotIn("Illustrazione generata con IA", payload["content"])

    def test_later_image_is_not_captured_by_a_broken_leading_marker(self):
        content = '<!-- wp:image {"id":42} -->' + self.body + self.cover
        self.assertEqual(repair.leading_cover(content), (None, ""))

    @patch.object(quality, "request_with_retry")
    def test_exposure_update_retains_the_caption_body_and_schedule(self, request):
        cover = repair.featured_image_block(self.media, "Alt originale", repair.CoverCredit("Credito originale"))
        post = self.post(cover + self.body + '<p><a href="https://www.amazon.it/?tag=lavocdelweb-21">Vedi</a></p>')
        post.update(date="2026-11-22T08:00:00", date_gmt="2026-11-22T07:00:00", slug="test")
        block, _ = repair.leading_cover(repair.raw_content(post))
        current, query, reread, write, after = [MagicMock() for _ in range(5)]
        request.side_effect = [current, query, reread, write, after]
        current.json.return_value = post
        reread.json.return_value = post
        query.json.return_value = [{"source_url": self.new_url, "id": 77}]
        new_cover = cover.replace(self.old_url, self.new_url).replace('"id":42', '"id":77').replace("wp-image-42", "wp-image-77")
        new_content = new_cover + repair.raw_content(post)[len(cover):]
        after.json.return_value = {**post, "featured_media": 77, "content": {"raw": new_content}}
        self.assertEqual(quality.update_cover(self.client, post, self.media, Image.new("RGB", (1280, 720)), block), 77)
        self.assertEqual(request.call_args_list[3].kwargs["json"], {"featured_media": 77, "content": new_content})


if __name__ == "__main__":
    unittest.main()
