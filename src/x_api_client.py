import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)


class XAPIClient:
    def __init__(self):
        self.base_url = "https://api.x.com/2"
        self.headers = {
            "Authorization": f"Bearer {settings.X_BEARER_TOKEN}",
            "Content-Type": "application/json",
        }

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """
        Get user information by username
        Returns user data including user_id
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/by/username/{username}",
                    headers=self.headers,
                )

                if response.status_code == 200:
                    data = response.json()
                    if "data" in data:
                        return data["data"]
                    return None
                elif response.status_code == 404:
                    logger.warning(f"User not found: {username}")
                    return None
                else:
                    logger.error(
                        f"X API error: {response.status_code} - {response.text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error fetching user {username}: {str(e)}")
            return None

    async def add_user_to_list(self, list_id: str, user_id: str) -> bool:
        """
        Add user to X list
        Returns True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/lists/{list_id}/members",
                    headers=self.headers,
                    json={"user_id": user_id},
                )

                if response.status_code == 200:
                    logger.info(f"Successfully added user {user_id} to list {list_id}")
                    return True
                elif response.status_code == 400:
                    # User might already be in the list
                    error_data = response.json()
                    if "already" in error_data.get("detail", "").lower():
                        logger.info(f"User {user_id} already in list {list_id}")
                        return True
                    else:
                        logger.error(f"Bad request: {error_data}")
                        return False
                else:
                    logger.error(
                        f"X API error: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error adding user {user_id} to list {list_id}: {str(e)}")
            return False

    async def get_list_members(self, list_id: str) -> list | None:
        """
        Get list members (for verification)
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/lists/{list_id}/members",
                    headers=self.headers,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                else:
                    logger.error(
                        f"Error fetching list members: {response.status_code} - {response.text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error fetching list members: {str(e)}")
            return None


# Global X API client instance
x_api_client = XAPIClient()
