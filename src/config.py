import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # X API Configuration
    X_BEARER_TOKEN: str = os.getenv("X_BEARER_TOKEN", "")
    X_LIST_ID: str = os.getenv("X_LIST_ID", "1979623501649567798")
    
    # X OAuth 1.0a Configuration (for list management)
    X_CONSUMER_KEY: str = os.getenv("X_CONSUMER_KEY", "")
    X_CONSUMER_SECRET: str = os.getenv("X_CONSUMER_SECRET", "")
    X_ACCESS_TOKEN: str = os.getenv("X_ACCESS_TOKEN", "")
    X_ACCESS_TOKEN_SECRET: str = os.getenv("X_ACCESS_TOKEN_SECRET", "")

    # Redis Configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # Rate limiting (15 minutes in seconds)
    RATE_LIMIT_SECONDS: int = 15 * 60


settings = Settings()
