import json
import time
import uuid
from typing import Dict, List, Optional

from config import MESSAGES, REDIS_EMAIL_KEY_PREFIX
from redis_service.redis_service import RedisService


CAMPAIGN_IDS_KEY = "campaign:ids"
DEFAULT_CAMPAIGN_ID = "default"


class CampaignStore:
    """Redis persistence and legacy-data migration for campaign workspaces."""

    def __init__(self, redis_service: Optional[RedisService] = None):
        self.redis_service = redis_service or RedisService()
        self.redis = self.redis_service.r

    @staticmethod
    def campaign_key(campaign_id: str) -> str:
        return f"campaign:{campaign_id}"

    @staticmethod
    def contacts_key(campaign_id: str) -> str:
        return f"campaign:{campaign_id}:contacts"

    @staticmethod
    def messages_key(campaign_id: str) -> str:
        return f"campaign:{campaign_id}:messages"

    def ensure_default_campaign(self) -> Dict:
        campaign = self.get_campaign(DEFAULT_CAMPAIGN_ID)
        if not campaign:
            campaign = {
                "campaign_id": DEFAULT_CAMPAIGN_ID,
                "name": "General Campaign",
                "description": "Existing contacts and message templates",
                "created_at": time.time(),
            }
            self.save_campaign(campaign)

        if not self.redis.exists(self.contacts_key(DEFAULT_CAMPAIGN_ID)):
            legacy_contacts = self.redis_service.get_data(REDIS_EMAIL_KEY_PREFIX) or []
            self.set_contacts(DEFAULT_CAMPAIGN_ID, legacy_contacts)
        if not self.redis.exists(self.messages_key(DEFAULT_CAMPAIGN_ID)):
            legacy_messages = self.redis_service.get_data(MESSAGES) or []
            self.set_messages(DEFAULT_CAMPAIGN_ID, legacy_messages)
        return campaign

    def save_campaign(self, campaign: Dict) -> None:
        pipeline = self.redis.pipeline()
        pipeline.set(self.campaign_key(campaign["campaign_id"]), json.dumps(campaign))
        pipeline.sadd(CAMPAIGN_IDS_KEY, campaign["campaign_id"])
        pipeline.execute()

    def create_campaign(self, name: str, description: str = "") -> Dict:
        campaign = {
            "campaign_id": str(uuid.uuid4()),
            "name": name.strip(),
            "description": description.strip(),
            "created_at": time.time(),
        }
        self.save_campaign(campaign)
        self.set_contacts(campaign["campaign_id"], [])
        self.set_messages(campaign["campaign_id"], [])
        return campaign

    def delete_campaign(self, campaign_id: str) -> None:
        """Remove a campaign and its campaign-owned contacts and templates."""
        pipeline = self.redis.pipeline()
        pipeline.delete(
            self.campaign_key(campaign_id),
            self.contacts_key(campaign_id),
            self.messages_key(campaign_id),
        )
        pipeline.srem(CAMPAIGN_IDS_KEY, campaign_id)
        pipeline.execute()

    def get_campaign(self, campaign_id: str) -> Optional[Dict]:
        value = self.redis.get(self.campaign_key(campaign_id))
        return json.loads(value) if value else None

    def list_campaigns(self) -> List[Dict]:
        self.ensure_default_campaign()
        campaigns = []
        for campaign_id in self.redis.smembers(CAMPAIGN_IDS_KEY):
            campaign = self.get_campaign(campaign_id)
            if not campaign:
                continue
            campaign["contact_count"] = len(self.get_contacts(campaign_id))
            campaign["message_count"] = len(self.get_messages(campaign_id))
            campaigns.append(campaign)
        return sorted(campaigns, key=lambda item: item.get("created_at", 0), reverse=True)

    def get_contacts(self, campaign_id: str) -> List[Dict]:
        return self.redis_service.get_data(self.contacts_key(campaign_id)) or []

    def set_contacts(self, campaign_id: str, contacts: List[Dict]) -> None:
        self.redis_service.set_data(self.contacts_key(campaign_id), contacts)

    def get_messages(self, campaign_id: str) -> List[Dict]:
        return self.redis_service.get_data(self.messages_key(campaign_id)) or []

    def set_messages(self, campaign_id: str, messages: List[Dict]) -> None:
        self.redis_service.set_data(self.messages_key(campaign_id), messages)
