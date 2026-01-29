import os
from dotenv import load_dotenv

load_dotenv()


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

BROKER_URL = f"redis://{REDIS_HOST}:6379/0"

REDIS_PORT = 6379

REDIS_DB = 0

REDIS_EMAIL_KEY_PREFIX = "email"

MESSAGES = "message"

AWS_REGION_NAME = os.getenv("AWS_REGION_NAME")

AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")

ZEPTO_API_KEY = os.getenv("ZEPTO_API_KEY")
