import json
from typing import Any

import redis.asyncio as redis

from config import settings


class RedisClient:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            decode_responses=True,
        )

    async def is_rate_limited(self, username: str) -> bool:
        """Check if user is rate limited (15 minutes)"""
        key = f"rate_limit:{username}"
        return await self.redis_client.exists(key) > 0

    async def set_rate_limit(self, username: str) -> None:
        """Set rate limit for user (15 minutes)"""
        key = f"rate_limit:{username}"
        await self.redis_client.setex(key, settings.RATE_LIMIT_SECONDS, "1")

    async def get_user_data(self, username: str) -> dict[str, Any] | None:
        """Get cached user data"""
        key = f"user_data:{username}"
        data = await self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_user_data(self, username: str, user_data: dict[str, Any]) -> None:
        """Cache user data for 1 hour"""
        key = f"user_data:{username}"
        await self.redis_client.setex(key, 3600, json.dumps(user_data))

    async def get_list_members(self, list_id: str) -> list:
        """Get cached list members"""
        key = f"list_members:{list_id}"
        data = await self.redis_client.get(key)
        if data:
            return json.loads(data)
        return []

    async def add_list_member(self, list_id: str, user_id: str) -> None:
        """Add member to cached list"""
        key = f"list_members:{list_id}"
        members = await self.get_list_members(list_id)
        if user_id not in members:
            members.append(user_id)
            await self.redis_client.setex(
                key,
                300,
                json.dumps(members),
            )  # Cache for 5 minutes

    async def store_username(self, username: str) -> None:
        """Store username in Redis with timestamp and 1 year TTL"""
        import datetime

        key = f"stored_username:{username}"
        timestamp = datetime.datetime.now().isoformat()
        data = {
            "username": username,
            "stored_at": timestamp,
        }
        # Store with 1 year TTL (365 days * 24 hours * 3600 seconds)
        await self.redis_client.setex(key, 365 * 24 * 3600, json.dumps(data))

    async def get_stored_username(self, username: str) -> dict[str, Any] | None:
        """Get stored username data"""
        key = f"stored_username:{username}"
        data = await self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None

    async def get_all_stored_usernames(self) -> list[dict[str, Any]]:
        """Get all stored usernames"""
        pattern = "stored_username:*"
        keys = await self.redis_client.keys(pattern)
        users = []

        for key in keys:
            data = await self.redis_client.get(key)
            if data:
                user_data = json.loads(data)
                users.append(user_data)

        return users

    async def health_check(self) -> bool:
        """Check Redis connection"""
        try:
            await self.redis_client.ping()
            return True
        except Exception:
            return False


# Global Redis client instance
redis_client = RedisClient()
