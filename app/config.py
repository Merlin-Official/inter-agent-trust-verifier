"""
Application configuration using Pydantic Settings.
Reads from environment variables / .env file.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./trust_verifier.db"

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Application
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Trust Engine
    REPUTATION_INITIAL_SCORE: float = 100.0
    REPUTATION_ACCEPT_BONUS: float = 1.0
    REPUTATION_REJECT_PENALTY: float = 5.0
    REPUTATION_SCRUTINY_THRESHOLD: float = 50.0

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
