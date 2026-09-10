import unittest

from email_threading import build_thread_headers
from template_renderer import (
    build_recipient_context,
    discover_template_variables,
    render_message_html,
    render_template_text,
)


class TemplateRendererTests(unittest.TestCase):
    def setUp(self):
        self.recipient = {
            "Name": "Ada Lovelace",
            "Emails": "ada@example.com",
            "Company": "Rooli & Co",
            "Name of Gp": "Alpha",
        }
        self.context = build_recipient_context(self.recipient)

    def test_builds_computed_and_csv_variables(self):
        self.assertEqual(self.context["first_name"], "Ada")
        self.assertEqual(self.context["last_name"], "Lovelace")
        self.assertEqual(self.context["email"], "ada@example.com")
        self.assertEqual(self.context["name_of_gp"], "Alpha")

    def test_renders_known_variables_and_keeps_unknown_variables_visible(self):
        result = render_template_text(
            "Hi {{first_name}} from {{company}} — {{unknown}}", self.context
        )
        self.assertEqual(result, "Hi Ada from Rooli & Co — {{unknown}}")

    def test_escapes_recipient_content_in_html_email(self):
        result = render_message_html("{{company}}\nWelcome", self.context)
        self.assertEqual(result, "Rooli &amp; Co<br>Welcome")

    def test_discovers_normalized_csv_columns(self):
        keys = {item["key"] for item in discover_template_variables([self.recipient])}
        self.assertIn("name_of_gp", keys)
        self.assertIn("first_name", keys)

    def test_builds_follow_up_thread_headers(self):
        previous_ids = ["<root@example.com>", "<follow-up@example.com>"]
        message_id, headers = build_thread_headers("sender@example.com", previous_ids)
        self.assertTrue(message_id.endswith("@example.com>"))
        self.assertEqual(headers["Message-ID"], message_id)
        self.assertEqual(headers["In-Reply-To"], previous_ids[-1])
        self.assertEqual(headers["References"], " ".join(previous_ids))


if __name__ == "__main__":
    unittest.main()
