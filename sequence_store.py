import json
import time
from typing import Dict, List, Optional

from redis_service.redis_service import RedisService


SEQUENCE_IDS_KEY = "sequence:ids"
SEQUENCE_DUE_KEY = "sequence:due"
SEQUENCE_INFLIGHT_KEY = "sequence:inflight"
SEQUENCE_DISPATCH_LOCK_KEY = "sequence:dispatch-lock"


class SequenceStore:
    """Redis persistence for sequences and per-recipient enrolments."""

    def __init__(self, redis_service: Optional[RedisService] = None):
        self.redis = (redis_service or RedisService()).r

    @staticmethod
    def sequence_key(sequence_id: str) -> str:
        return f"sequence:{sequence_id}"

    @staticmethod
    def enrollment_key(enrollment_id: str) -> str:
        return f"sequence:enrollment:{enrollment_id}"

    def save_sequence(self, sequence: Dict) -> None:
        pipeline = self.redis.pipeline()
        pipeline.set(self.sequence_key(sequence["sequence_id"]), json.dumps(sequence))
        pipeline.sadd(SEQUENCE_IDS_KEY, sequence["sequence_id"])
        pipeline.execute()

    def get_sequence(self, sequence_id: str) -> Optional[Dict]:
        value = self.redis.get(self.sequence_key(sequence_id))
        return json.loads(value) if value else None

    def list_sequences(self, campaign_id: Optional[str] = None) -> List[Dict]:
        sequences = []
        for sequence_id in self.redis.smembers(SEQUENCE_IDS_KEY):
            sequence = self.get_sequence(sequence_id)
            sequence_campaign_id = sequence.get("campaign_id", "default") if sequence else None
            if sequence and (campaign_id is None or sequence_campaign_id == campaign_id):
                sequences.append(sequence)
        return sorted(sequences, key=lambda item: item.get("created_at", 0), reverse=True)

    def delete_campaign_sequences(self, campaign_id: str) -> Dict[str, int]:
        """Remove sequences, enrollments, and schedule entries owned by a campaign."""
        sequences = self.list_sequences(campaign_id)
        enrollment_ids = [
            enrollment_id
            for sequence in sequences
            for enrollment_id in sequence.get("enrollment_ids", [])
        ]
        pipeline = self.redis.pipeline()
        for enrollment_id in enrollment_ids:
            pipeline.zrem(SEQUENCE_DUE_KEY, enrollment_id)
            pipeline.zrem(SEQUENCE_INFLIGHT_KEY, enrollment_id)
            pipeline.delete(self.enrollment_key(enrollment_id))
        for sequence in sequences:
            sequence_id = sequence["sequence_id"]
            pipeline.delete(self.sequence_key(sequence_id))
            pipeline.srem(SEQUENCE_IDS_KEY, sequence_id)
        pipeline.execute()
        return {"sequences": len(sequences), "enrollments": len(enrollment_ids)}

    def get_delivery_summary(self, campaign_id: str) -> Dict:
        totals = {
            "planned_messages": 0,
            "sent_messages": 0,
            "not_sent_messages": 0,
            "failed_messages": 0,
            "active_recipients": 0,
            "completed_recipients": 0,
            "suppressed_recipients": 0,
        }
        sequence_summaries = []
        deliveries = []

        for sequence in self.list_sequences(campaign_id):
            step_count = len(sequence.get("steps", []))
            summary = {
                "sequence_id": sequence["sequence_id"],
                "name": sequence.get("name", "Untitled sequence"),
                "status": sequence.get("status", "unknown"),
                "created_at": sequence.get("created_at"),
                "step_count": step_count,
                "enrolled": sequence.get("enrolled", 0),
                "sent_messages": 0,
                "not_sent_messages": 0,
                "failed_messages": 0,
            }

            for enrollment_id in sequence.get("enrollment_ids", []):
                enrollment = self.get_enrollment(enrollment_id)
                if not enrollment:
                    continue
                sent_count = len(enrollment.get("history", []))
                not_sent_count = max(step_count - sent_count, 0)
                enrollment_status = enrollment.get("status", "scheduled")
                failed_count = not_sent_count if enrollment_status == "failed" else 0
                history = enrollment.get("history", [])
                last_sent_at = history[-1].get("sent_at") if history else None
                recipient = enrollment.get("recipient", {})

                totals["planned_messages"] += step_count
                totals["sent_messages"] += sent_count
                totals["not_sent_messages"] += not_sent_count
                totals["failed_messages"] += failed_count
                if enrollment_status == "completed":
                    totals["completed_recipients"] += 1
                elif enrollment_status == "suppressed":
                    totals["suppressed_recipients"] += 1
                elif enrollment_status not in {"failed", "cancelled"}:
                    totals["active_recipients"] += 1

                summary["sent_messages"] += sent_count
                summary["not_sent_messages"] += not_sent_count
                summary["failed_messages"] += failed_count
                deliveries.append({
                    "enrollment_id": enrollment_id,
                    "sequence_id": sequence["sequence_id"],
                    "sequence_name": sequence.get("name", "Untitled sequence"),
                    "recipient_name": recipient.get("Name", recipient.get("name", "")),
                    "recipient_email": recipient.get("Emails", recipient.get("email", "")),
                    "sender": enrollment.get("sender"),
                    "status": enrollment_status,
                    "sent_messages": sent_count,
                    "not_sent_messages": not_sent_count,
                    "last_sent_at": last_sent_at,
                    "next_run_at": enrollment.get("next_run_at"),
                    "last_error": enrollment.get("last_error"),
                })

            sequence_summaries.append(summary)

        deliveries.sort(
            key=lambda item: item.get("last_sent_at") or item.get("next_run_at") or 0,
            reverse=True,
        )
        return {
            "totals": totals,
            "sequences": sequence_summaries,
            "deliveries": deliveries[:250],
        }

    def save_enrollment(self, enrollment: Dict) -> None:
        self.redis.set(self.enrollment_key(enrollment["enrollment_id"]), json.dumps(enrollment))

    def get_enrollment(self, enrollment_id: str) -> Optional[Dict]:
        value = self.redis.get(self.enrollment_key(enrollment_id))
        return json.loads(value) if value else None

    def schedule_enrollment(self, enrollment: Dict, due_at: float) -> None:
        enrollment["next_run_at"] = due_at
        enrollment["status"] = "scheduled"
        pipeline = self.redis.pipeline()
        pipeline.set(self.enrollment_key(enrollment["enrollment_id"]), json.dumps(enrollment))
        pipeline.zrem(SEQUENCE_INFLIGHT_KEY, enrollment["enrollment_id"])
        pipeline.zadd(SEQUENCE_DUE_KEY, {enrollment["enrollment_id"]: due_at})
        pipeline.execute()

    def claim_due_enrollments(self, limit: int = 1) -> List[str]:
        now = time.time()
        expired_ids = self.redis.zrangebyscore(SEQUENCE_INFLIGHT_KEY, 0, now)
        for enrollment_id in expired_ids:
            self.redis.eval(
                """
                if redis.call('zrem', KEYS[1], ARGV[1]) == 1 then
                    redis.call('zadd', KEYS[2], ARGV[2], ARGV[1])
                end
                """,
                2,
                SEQUENCE_INFLIGHT_KEY,
                SEQUENCE_DUE_KEY,
                enrollment_id,
                now,
            )

        due_ids = self.redis.zrangebyscore(SEQUENCE_DUE_KEY, 0, now, start=0, num=limit)
        if due_ids and not self.redis.set(SEQUENCE_DISPATCH_LOCK_KEY, "1", nx=True, ex=60):
            return []
        claimed = []
        for enrollment_id in due_ids:
            was_claimed = self.redis.eval(
                """
                if redis.call('zrem', KEYS[1], ARGV[1]) == 1 then
                    redis.call('zadd', KEYS[2], ARGV[2], ARGV[1])
                    return 1
                end
                return 0
                """,
                2,
                SEQUENCE_DUE_KEY,
                SEQUENCE_INFLIGHT_KEY,
                enrollment_id,
                now + 300,
            )
            if was_claimed:
                claimed.append(enrollment_id)
        return claimed

    def acknowledge_enrollment(self, enrollment_id: str) -> None:
        self.redis.zrem(SEQUENCE_INFLIGHT_KEY, enrollment_id)

    def remove_from_schedule(self, enrollment_id: str) -> None:
        pipeline = self.redis.pipeline()
        pipeline.zrem(SEQUENCE_DUE_KEY, enrollment_id)
        pipeline.zrem(SEQUENCE_INFLIGHT_KEY, enrollment_id)
        pipeline.execute()

    def lock_enrollment(self, enrollment_id: str):
        return self.redis.lock(f"sequence:lock:{enrollment_id}", timeout=120, blocking_timeout=1)
