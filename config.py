import os
from dotenv import load_dotenv

load_dotenv()


BROKER_URL = "redis://localhost:6379/0"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_EMAIL_KEY_PREFIX = "email"

AWS_REGION_NAME = os.getenv("AWS_REGION_NAME")

AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
