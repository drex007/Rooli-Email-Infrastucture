import unittest

from email_providers.aws_ses_provider import EmailTemplateEditor
from suppression_store import SuppressionStore, build_unsubscribe_headers


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.hashes = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = value

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    def hexists(self, key, field):
        return field in self.hashes.get(key, {})


class FakeRedisService:
    def __init__(self):
        self.r = FakeRedis()


class SuppressionStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = SuppressionStore(FakeRedisService())

    def test_creates_opaque_token_and_resolves_recipient(self):
        token = self.store.create_unsubscribe_token("Person@Example.com", "campaign-1")

        self.assertNotIn("person@example.com", token)
        self.assertEqual(
            self.store.resolve_unsubscribe_token(token),
            {"email": "person@example.com", "campaign_id": "campaign-1"},
        )

    def test_suppression_is_global_and_case_insensitive(self):
        record = self.store.suppress("Person@Example.com", campaign_id="campaign-1")

        self.assertEqual(record["email"], "person@example.com")
        self.assertTrue(self.store.is_suppressed("PERSON@example.com"))

    def test_builds_rfc_8058_one_click_headers(self):
        headers = build_unsubscribe_headers("https://api.example.com/unsubscribe/token")

        self.assertEqual(
            headers["List-Unsubscribe"],
            "<https://api.example.com/unsubscribe/token>",
        )
        self.assertEqual(
            headers["List-Unsubscribe-Post"],
            "List-Unsubscribe=One-Click",
        )

    def test_email_template_contains_identity_contact_and_unsubscribe_link(self):
        html = EmailTemplateEditor().edit_template_and_return_body(
            "email_test.html",
            {
                "subject": "Hello",
                "message": "Message body",
                "business_name": "Example Ltd",
                "business_copyright": "© 2026 Example Ltd. All rights reserved.",
                "business_address": "1 Example Street",
                "business_contact_email": "support@example.com",
                "business_website_url": "https://example.com",
                "unsubscribe_url": "https://api.example.com/unsubscribe/token",
            },
        )

        self.assertIn("© 2026 Example Ltd. All rights reserved.", html)
        self.assertIn("1 Example Street", html)
        self.assertIn("support@example.com", html)
        self.assertIn("https://api.example.com/unsubscribe/token", html)
        self.assertNotIn("telephone", html.lower())


if __name__ == "__main__":
    unittest.main()
