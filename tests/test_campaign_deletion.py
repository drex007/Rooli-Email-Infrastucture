import unittest
from unittest.mock import Mock, call

from campaign_store import CAMPAIGN_IDS_KEY, CampaignStore
from sequence_store import (
    SEQUENCE_DUE_KEY,
    SEQUENCE_IDS_KEY,
    SEQUENCE_INFLIGHT_KEY,
    SequenceStore,
)


class CampaignDeletionTests(unittest.TestCase):
    def test_deletes_campaign_contacts_and_messages(self):
        service = Mock()
        pipeline = Mock()
        service.r.pipeline.return_value = pipeline
        store = CampaignStore(service)

        store.delete_campaign("campaign-1")

        pipeline.delete.assert_called_once_with(
            "campaign:campaign-1",
            "campaign:campaign-1:contacts",
            "campaign:campaign-1:messages",
        )
        pipeline.srem.assert_called_once_with(CAMPAIGN_IDS_KEY, "campaign-1")
        pipeline.execute.assert_called_once_with()

    def test_deletes_campaign_sequences_enrollments_and_schedules(self):
        service = Mock()
        pipeline = Mock()
        service.r.pipeline.return_value = pipeline
        store = SequenceStore(service)
        store.list_sequences = Mock(return_value=[{
            "sequence_id": "sequence-1",
            "enrollment_ids": ["enrollment-1", "enrollment-2"],
        }])

        deleted = store.delete_campaign_sequences("campaign-1")

        self.assertEqual(deleted, {"sequences": 1, "enrollments": 2})
        self.assertEqual(
            pipeline.zrem.call_args_list,
            [
                call(SEQUENCE_DUE_KEY, "enrollment-1"),
                call(SEQUENCE_INFLIGHT_KEY, "enrollment-1"),
                call(SEQUENCE_DUE_KEY, "enrollment-2"),
                call(SEQUENCE_INFLIGHT_KEY, "enrollment-2"),
            ],
        )
        self.assertEqual(
            pipeline.delete.call_args_list,
            [
                call("sequence:enrollment:enrollment-1"),
                call("sequence:enrollment:enrollment-2"),
                call("sequence:sequence-1"),
            ],
        )
        pipeline.srem.assert_called_once_with(SEQUENCE_IDS_KEY, "sequence-1")
        pipeline.execute.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
