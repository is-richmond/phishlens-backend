"""
PhishLens Core Configuration

Application settings loaded from environment variables.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    # Application
    app_name: str = "PhishLens API"
    app_version: str = "1.0.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")

    # Database
    database_url: str = Field(
        default="postgresql://phishlens_user:phishlens_dev_password@localhost:5432/phishlens_db",
        alias="DATABASE_URL",
    )

    # JWT Authentication
    secret_key: str = Field(
        default="dev-secret-key-change-in-production", alias="SECRET_KEY"
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # Google Gemini
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")

    # CORS
    frontend_url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")

    # Rate Limiting
    rate_limit_researcher: int = Field(default=30, alias="RATE_LIMIT_RESEARCHER")
    rate_limit_admin: int = Field(default=100, alias="RATE_LIMIT_ADMIN")

    # Ethical Safeguards
    terms_validity_days: int = Field(default=90, alias="TERMS_VALIDITY_DAYS")
    abuse_detection_std_devs: float = Field(
        default=2.0, alias="ABUSE_DETECTION_STD_DEVS"
    )

    # Data Retention
    retention_generation_months: int = Field(
        default=12, alias="RETENTION_GENERATION_MONTHS"
    )
    retention_inactive_user_months: int = Field(
        default=6, alias="RETENTION_INACTIVE_USER_MONTHS"
    )

    # Encryption (AES-256 for API keys at rest)
    api_key_encryption_key: Optional[str] = Field(
        default=None, alias="API_KEY_ENCRYPTION_KEY"
    )

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Singleton settings instance
settings = Settings()
