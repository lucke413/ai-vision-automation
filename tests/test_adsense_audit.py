import unittest
from scripts.adsense_audit import html_signals, account_check

PUB = 'pub-1234567890123456'


class AccountTests(unittest.TestCase):
    def test_platform_and_plain_text_are_not_owner_proof(self):
        signals = html_signals({'text': f'<meta name="google-adsense-platform-account" content="ca-{PUB}"><p>{PUB}</p>'})
        self.assertEqual(account_check(signals, {}, PUB)['status'], 'not_found')

    def test_meta_and_script_are_recognized(self):
        for html in (
            f'<meta content="ca-{PUB}" name="google-adsense-account">',
            f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-{PUB}"></script>',
        ):
            self.assertEqual(account_check(html_signals({'text': html}), {}, PUB)['status'], 'public_match')

    def test_wrong_account_does_not_pass(self):
        self.assertEqual(account_check({'account_publisher_ids': ['pub-9999999999999999']}, {}, PUB)['status'], 'not_found')

    def test_missing_and_invalid_configuration(self):
        self.assertEqual(account_check({}, {}, '')['status'], 'not_configured')
        self.assertEqual(account_check({}, {}, 'pub-123')['status'], 'invalid_configuration')

    def test_reseller_is_not_direct_owner_proof(self):
        self.assertEqual(account_check({}, {'publisher_ids': [PUB]}, PUB)['status'], 'not_found')
        self.assertEqual(account_check({}, {'direct_publisher_ids': [PUB]}, PUB)['status'], 'public_match')

    def test_unrelated_script_is_ignored(self):
        html = f'<script src="https://example.com/adsbygoogle.js?client=ca-{PUB}"></script>'
        self.assertEqual(account_check(html_signals({'text': html}), {}, PUB)['status'], 'not_found')
