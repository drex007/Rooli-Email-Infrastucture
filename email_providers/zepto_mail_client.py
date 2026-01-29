import requests
from typing import List, Dict, Optional

from config import ZEPTO_API_KEY


class ZeptoMailClient:
    BASE_URL = "https://api.zeptomail.com/v1.1/email"

    def __init__(
        self,
        domain: str = None,
        send_mail_token: str = ZEPTO_API_KEY,
    ):
        """
        :param send_mail_token: ZeptoMail SEND_MAIL_TOKEN
        :param domain: Verified sender domain (e.g. noreply@roolimarketing.xyz)
        """
        self.send_mail_token = send_mail_token
        self.domain = domain

        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self.send_mail_token,
        }

    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        html_body: str,
        name: Optional[str] = "",
        from_address: Optional[str] = None,
        cc: Optional[List[Dict[str, str]]] = None,
        bcc: Optional[List[Dict[str, str]]] = None,
        reply_to: Optional[str] = None,
    ) -> Dict:
        """
        Send transactional email via ZeptoMail

        to_emails format:
        [
            {"address": "user@example.com", "name": "User Name"}
        ]
        """

        payload = {
            "from": {
                "address": from_address or self.domain,
            },
            "to": [{"email_address": {"address": email, "name": name}} for email in to_emails],
            "subject": subject,
            "htmlbody": html_body,
        }

        if cc:
            payload["cc"] = [{"email_address": email} for email in cc]

        if bcc:
            payload["bcc"] = [{"email_address": email} for email in bcc]

        if reply_to:
            payload["reply_to"] = {"address": reply_to}

        response = requests.post(self.BASE_URL, headers=self.headers, json=payload, timeout=15)

        try:
            res = response.json()
            print(res, "ZEPTO MAIL RESPONSE")
            return {"status": "success"}

        except Exception as e:
            print(e, "ZEPTO MAIL ERROR")
            return {"status": "failure"}
