import hashlib
import hmac
import json
import secrets
import time
from typing import Dict, Optional

from config import PUBLIC_API_URL, UNSUBSCRIBE_SECRET
from redis_service.redis_service import RedisService


SUPPRESSION_KEY = "email:suppressions"
UNSUBSCRIBE_TOKENS_KEY = "email:unsubscribe:tokens"
UNSUBSCRIBE_SECRET_KEY = "email:unsubscribe:secret"


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


class SuppressionStore:
    """Redis-backed unsubscribe tokens and global email suppression state."""

    def __init__(self, redis_service: Optional[RedisService] = None):
        self.redis = (redis_service or RedisService()).r

    def _signing_secret(self) -> str:
        if UNSUBSCRIBE_SECRET:
            return UNSUBSCRIBE_SECRET
        existing = self.redis.get(UNSUBSCRIBE_SECRET_KEY)
        if existing:
            return existing
        generated = secrets.token_urlsafe(48)
        self.redis.set(UNSUBSCRIBE_SECRET_KEY, generated, nx=True)
        return self.redis.get(UNSUBSCRIBE_SECRET_KEY) or generated

    def create_unsubscribe_token(self, email: str, campaign_id: str = "default") -> str:
        normalized_email = normalize_email(email)
        if not normalized_email:
            raise ValueError("An email address is required to create an unsubscribe token.")
        message = f"{campaign_id}\0{normalized_email}".encode("utf-8")
        token = hmac.new(
            self._signing_secret().encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()
        self.redis.hset(
            UNSUBSCRIBE_TOKENS_KEY,
            token,
            json.dumps({"email": normalized_email, "campaign_id": campaign_id}),
        )
        return token

    def resolve_unsubscribe_token(self, token: str) -> Optional[Dict[str, str]]:
        value = self.redis.hget(UNSUBSCRIBE_TOKENS_KEY, token)
        return json.loads(value) if value else None

    def unsubscribe_url(self, email: str, campaign_id: str = "default") -> str:
        token = self.create_unsubscribe_token(email, campaign_id)
        return f"{PUBLIC_API_URL}/unsubscribe/{token}"

    def suppress(
        self,
        email: str,
        reason: str = "unsubscribe",
        campaign_id: str = "default",
        source: str = "recipient",
    ) -> Dict:
        normalized_email = normalize_email(email)
        if not normalized_email:
            raise ValueError("An email address is required to create a suppression.")
        record = {
            "email": normalized_email,
            "reason": reason,
            "campaign_id": campaign_id,
            "source": source,
            "created_at": time.time(),
        }
        self.redis.hset(SUPPRESSION_KEY, normalized_email, json.dumps(record))
        return record

    def is_suppressed(self, email: str) -> bool:
        normalized_email = normalize_email(email)
        return bool(normalized_email and self.redis.hexists(SUPPRESSION_KEY, normalized_email))

    def get_suppression(self, email: str) -> Optional[Dict]:
        value = self.redis.hget(SUPPRESSION_KEY, normalize_email(email))
        return json.loads(value) if value else None


def build_unsubscribe_headers(unsubscribe_url: str) -> Dict[str, str]:
    return {
        "List-Unsubscribe": f"<{unsubscribe_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
