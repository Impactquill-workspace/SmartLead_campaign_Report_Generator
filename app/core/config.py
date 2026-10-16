from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    smartlead_api_key: str = Field(default="", alias="SMARTLEAD_API_KEY")
    api_base_url: str = Field(default="https://server.smartlead.ai/api/v1", alias="API_BASE_URL")
    database_url: str = Field(
        default="sqlite:///./smartlead_analytics.db",
        alias="DATABASE_URL",
        description="Database URL (PostgreSQL or SQLite)"
    )
    smartlead_max_concurrency: int = Field(default=5, alias="SMARTLEAD_MAX_CONCURRENCY")
    dry_run: bool = Field(default=True, alias="DRY_RUN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    report_day: str = Field(default="MONDAY", alias="REPORT_DAY")
    report_hour: int = Field(default=9, alias="REPORT_HOUR")
    report_minute: int = Field(default=0, alias="REPORT_MINUTE")
    request_timeout: float = Field(default=30.0, alias="REQUEST_TIMEOUT")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    base_backoff_seconds: float = Field(default=1.0, alias="BASE_BACKOFF_SECONDS")
    webhook_secret: Optional[str] = Field(default=None, alias="WEBHOOK_SECRET")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def masked_api_key(self) -> str:
        """Returns safe masked representation of the API key without revealing secret."""
        if not self.smartlead_api_key or len(self.smartlead_api_key.strip()) == 0:
            return "[NOT CONFIGURED]"
        cleaned = self.smartlead_api_key.strip()
        if len(cleaned) <= 6:
            return "***"
        return f"{cleaned[:2]}***{cleaned[-3:]}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
