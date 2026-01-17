import redis
import json


class RedisService:
    pass
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.r = redis.Redis(host=self.redis_host, port=self.redis_port, db=self.redis_db, decode_responses=True)
     
    def get_data(self, key: str) -> list:
        """Get data from Redis and parse JSON string"""
        try:
            value = self.r.get(key)
            if value:
                value = json.loads(value)
                print(f"✓ Retrieved data for key: {key}")
                return value
            else:
                print(f"✗ No data found for key: {key}")
                return []
        except Exception as e:
            print(f"✗ Error retrieving data for key {key}: {e}")
            return []

    def set_data(self, key: str, value: list) -> None:
        """Set data in Redis as JSON string"""
        try:
            value = json.dumps(value)
            self.r.set(key, value)
            print(f"✓ Set data for key: {key}")
        except Exception as e:
            print(f"✗ Error setting data for key {key}: {e}")