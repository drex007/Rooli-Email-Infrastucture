import os
from dotenv import load_dotenv

load_dotenv()



REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

BROKER_URL = f"redis://{REDIS_HOST}:6379/0"

REDIS_PORT = 6379

REDIS_DB = 0

REDIS_EMAIL_KEY_PREFIX = "email"

MESSAGES = "message"

SENDERS = "senders"

AWS_REGION_NAME = os.getenv("AWS_REGION_NAME")

AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")

ZEPTO_API_KEY = os.getenv("ZEPTO_API_KEY")

PUBLIC_API_URL = (os.getenv("PUBLIC_API_URL") or "http://localhost:8000").rstrip("/")
UNSUBSCRIBE_SECRET = os.getenv("UNSUBSCRIBE_SECRET") or None

BUSINESS_NAME = os.getenv("BUSINESS_NAME") or "Rooli"
BUSINESS_COPYRIGHT = (
    os.getenv("BUSINESS_COPYRIGHT")
    or "© 2026 Rooli — A Cresthub Media Limited Company. All rights reserved."
)
BUSINESS_ADDRESS = os.getenv("BUSINESS_ADDRESS") or ""
BUSINESS_CONTACT_EMAIL = os.getenv("BUSINESS_CONTACT_EMAIL") or "marketing@roolimarketing.xyz"
BUSINESS_WEBSITE_URL = os.getenv("BUSINESS_WEBSITE_URL") or "https://rooli.co/"
