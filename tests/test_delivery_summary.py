import unittest

from sequence_store import SequenceStore


class DeliverySummaryTests(unittest.TestCase):
    def test_counts_sent_unsent_and_failed_messages(self):
        store = SequenceStore.__new__(SequenceStore)
        store.list_sequences = lambda campaign_id: [
            {
                "sequence_id": "sequence-1",
                "campaign_id": campaign_id,
                "name": "Investor follow-up",
                "status": "active",
                "created_at": 100,
                "steps": [{}, {}, {}],
                "enrolled": 2,
                "enrollment_ids": ["completed", "failed"],
            }
        ]
        enrollments = {
            "completed": {
                "status": "completed",
                "recipient": {"Name": "Ada", "Emails": "ada@example.com"},
                "history": [{"sent_at": 1}, {"sent_at": 2}, {"sent_at": 3}],
            },
            "failed": {
                "status": "failed",
                "recipient": {"Name": "Grace", "Emails": "grace@example.com"},
                "history": [{"sent_at": 1}],
                "last_error": "Provider rejected message",
            },
        }
        store.get_enrollment = enrollments.get

        summary = store.get_delivery_summary("campaign-1")

        self.assertEqual(summary["totals"]["planned_messages"], 6)
        self.assertEqual(summary["totals"]["sent_messages"], 4)
        self.assertEqual(summary["totals"]["not_sent_messages"], 2)
        self.assertEqual(summary["totals"]["failed_messages"], 2)
        self.assertEqual(summary["totals"]["completed_recipients"], 1)


if __name__ == "__main__":
    unittest.main()
