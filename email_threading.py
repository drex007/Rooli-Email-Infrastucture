import uuid
from typing import Dict, List, Tuple


def create_message_id(sender: str) -> str:
    domain = sender.split("@", 1)[1] if "@" in sender else "roolimarketing.xyz"
    return f"<{uuid.uuid4()}@{domain}>"


def build_thread_headers(sender: str, sent_message_ids: List[str]) -> Tuple[str, Dict[str, str]]:
    message_id = create_message_id(sender)
    headers = {"Message-ID": message_id}
    if sent_message_ids:
        headers["In-Reply-To"] = sent_message_ids[-1]
        headers["References"] = " ".join(sent_message_ids)
    return message_id, headers
