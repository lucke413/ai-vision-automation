import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import wp_publisher as publisher


class PublicSourceFooterTests(unittest.TestCase):
    def test_removes_standalone_source_reference_at_end(self):
        body = (
            "## Autonomia\n"
            "La batteria dura a lungo. Tom's Hardware ha misurato circa venti giorni.\n\n"
            "Fonte di riferimento: [Tom's Hardware Italia](https://example.com/review)."
        )
        cleaned = publisher.strip_public_source_notes(body)
        self.assertIn("Tom's Hardware ha misurato circa venti giorni", cleaned)
        self.assertNotIn("Fonte di riferimento", cleaned)
        self.assertNotIn("https://example.com/review", cleaned)

    def test_keeps_inline_attribution_and_non_terminal_mentions(self):
        body = (
            "Tom's Hardware segnala alcuni limiti nel conteggio dei passi.\n\n"
            "Questi dati aiutano a interpretare il prodotto."
        )
        self.assertEqual(publisher.strip_public_source_notes(body), body)

    def test_does_not_remove_a_source_label_in_the_middle(self):
        body = (
            "Fonte: documento del produttore.\n\n"
            "Il testo prosegue con una spiegazione utile."
        )
        self.assertEqual(publisher.strip_public_source_notes(body), body)


if __name__ == "__main__":
    unittest.main()
