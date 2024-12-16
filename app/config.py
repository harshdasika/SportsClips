from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # AWS
    AWS_ACCESS_KEY: SecretStr
    AWS_SECRET_KEY: SecretStr
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = "sports-clips-videos"

    OLLAMA_API_URL: str = "http://localhost:11434"

    class Config:
        env_file = ".env"  # Load variables from .env file


@lru_cache()
def get_settings():
    """
    Load settings using LRU cache for efficiency.
    Clear the cache if new values need to be loaded dynamically.
    """
    return Settings()


# Initialize settings
# Uncomment if needed to reload the environment variables dynamically
# get_settings.cache_clear()

settings = get_settings()
