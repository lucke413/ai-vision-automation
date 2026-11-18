import unittest
from unittest.mock import MagicMock, patch

from scripts import inline_image_repair as repair


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
        self.assertIsNone(repair.repair_post(self.client, self.post(self.cover + self.body), {}))
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
    def test_replaces_both_covers_without_touching_body_or_schedule(self, request, _):
        post = self.post(self.cover + self.body)
        new_media = {"id": 77, "source_url": self.new_url}
        self.client.upload_media.return_value = new_media
        response = MagicMock()
        saved = MagicMock()
        saved.json.return_value = {
            "status": "future", "featured_media": 77,
            "content": {"raw": repair.featured_image_block(new_media, "Titolo") + "\n\n" + self.body},
        }
        current = MagicMock()
        current.json.return_value = post
        empty = MagicMock()
        empty.json.return_value = []
        request.side_effect = [current, empty, response, saved]
        result = repair.repair_post(self.client, post, {})
        payload = request.call_args_list[2].kwargs["json"]
        self.assertEqual(set(payload), {"content", "featured_media", "meta"})
        self.assertEqual(payload["featured_media"], 77)
        self.assertIn(self.new_url, payload["content"])
        self.assertNotIn(self.old_url, payload["content"])
        self.assertTrue(payload["content"].endswith(self.body))
        self.assertEqual(result["status"], "future")

    def test_later_image_is_not_captured_by_a_broken_leading_marker(self):
        content = '<!-- wp:image {"id":42} -->' + self.body + self.cover
        self.assertEqual(repair.leading_cover(content), (None, ""))


if __name__ == "__main__":
    unittest.main()
