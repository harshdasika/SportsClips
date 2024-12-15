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
    S3_BUCKET: str

    # Audio Processing
    SAMPLE_RATE: int = 22050
    HOP_LENGTH: int = 512

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
