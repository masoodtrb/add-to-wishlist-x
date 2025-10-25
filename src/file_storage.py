import json
from datetime import datetime
from pathlib import Path
from typing import Any


class FileStorage:
    """File-based storage for usernames as a temporary solution"""

    def __init__(self, storage_file: str = "stored_usernames.json"):
        # Use /app/data directory in Docker, current directory otherwise
        if Path("/app/data").exists():
            # Running in Docker
            self.storage_file = f"/app/data/{storage_file}"
        else:
            # Running locally
            self.storage_file = f"./data/{storage_file}"

        self.ensure_storage_file()

    def ensure_storage_file(self) -> None:
        """Ensure the storage file exists - only create if truly missing"""
        storage_path = Path(self.storage_file)

        # Only create the file if it doesn't exist at all
        if not storage_path.exists():
            # Create parent directory if it doesn't exist
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            # Only create empty file if it's truly new
            with storage_path.open("w") as f:
                json.dump([], f)
        # If file exists, don't touch it - preserve existing data

    def load_usernames(self) -> list[dict[str, Any]]:
        """Load usernames from file"""
        try:
            with Path(self.storage_file).open() as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_usernames(self, usernames: list[dict[str, Any]]) -> None:
        """Save usernames to file"""
        with Path(self.storage_file).open("w") as f:
            json.dump(usernames, f, indent=2)

    def store_username(self, username: str) -> bool:
        """Store username in file with timestamp.

        Returns True if stored, False if already exists
        """
        usernames = self.load_usernames()

        # Check if username already exists
        existing_usernames = [u["username"] for u in usernames]
        if username.lower() not in [u.lower() for u in existing_usernames]:
            user_data = {
                "username": username,
                "stored_at": datetime.now().isoformat(),
            }
            usernames.append(user_data)
            self.save_usernames(usernames)
            return True
        return False

    def get_stored_username(self, username: str) -> dict[str, Any] | None:
        """Get stored username data"""
        usernames = self.load_usernames()
        for user in usernames:
            if user["username"].lower() == username.lower():
                return user
        return None

    def get_all_stored_usernames(self) -> list[dict[str, Any]]:
        """Get all stored usernames"""
        return self.load_usernames()

    def username_exists(self, username: str) -> bool:
        """Check if a username is stored"""
        usernames = self.load_usernames()
        return any(user["username"].lower() == username.lower() for user in usernames)

    def get_stored_usernames_count(self) -> int:
        """Get the count of stored usernames"""
        return len(self.load_usernames())

    def backup_stored_usernames(self) -> dict[str, Any]:
        """Create a backup of all stored usernames"""
        usernames = self.get_all_stored_usernames()
        return {
            "backup_created_at": datetime.now().isoformat(),
            "total_count": len(usernames),
            "usernames": usernames,
        }

    def health_check(self) -> bool:
        """Check if file storage is working"""
        try:
            self.load_usernames()
            return True
        except Exception:
            return False


# Global file storage instance
file_storage = FileStorage()
