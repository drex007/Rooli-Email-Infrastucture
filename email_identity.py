from typing import Dict

from config import (
    BUSINESS_ADDRESS,
    BUSINESS_CONTACT_EMAIL,
    BUSINESS_COPYRIGHT,
    BUSINESS_NAME,
    BUSINESS_WEBSITE_URL,
)


def get_business_identity(sender: str = "") -> Dict[str, str]:
    return {
        "business_name": BUSINESS_NAME,
        "business_copyright": BUSINESS_COPYRIGHT,
        "business_address": BUSINESS_ADDRESS,
        "business_contact_email": BUSINESS_CONTACT_EMAIL or sender,
        "business_website_url": BUSINESS_WEBSITE_URL,
    }
