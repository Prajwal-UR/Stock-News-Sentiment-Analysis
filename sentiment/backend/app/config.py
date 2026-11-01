from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    enable_demo_mode: bool = False
    news_provider: str = "newsapi"
    news_api_key: str = ""
    news_max_age_days: int = Field(default=30, ge=1, le=3650)
    gnews_api_key: str = ""
    gnews_max_age_days: int = Field(default=30, ge=0, le=3650)
    gnews_page_size: int = Field(default=10, ge=1, le=100)
    gnews_request_interval_seconds: float = Field(default=1.0, ge=0, le=10)
    finbert_model: str = "ProsusAI/finbert"
    frontend_origins: str = ""
    news_cache_ttl_seconds: int = Field(default=300, ge=0, le=3600)
    request_timeout_seconds: float = Field(default=12.0, gt=0, le=60)
    min_articles_for_conclusion: int = Field(default=3, ge=1, le=20)
    max_articles_per_request: int = Field(default=100, ge=1, le=100)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        configured = [origin.strip().rstrip("/") for origin in self.frontend_origins.split(",") if origin.strip()]
        if configured:
            return configured
        if self.app_env.casefold() == "development":
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        return []

    @property
    def news_available(self) -> bool:
        provider = self.news_provider.casefold()
        if provider == "newsapi":
            return bool(self.news_api_key.strip())
        if provider == "gnews":
            return bool(self.gnews_api_key.strip())
        return False

    @property
    def news_provider_display_name(self) -> str:
        return {"newsapi": "NewsAPI", "gnews": "GNews"}.get(
            self.news_provider.casefold(), self.news_provider
        )

    @property
    def provider_max_age_days(self) -> int:
        return (
            self.gnews_max_age_days
            if self.news_provider.casefold() == "gnews"
            else self.news_max_age_days
        )

    @property
    def demo_mode_available(self) -> bool:
        return self.enable_demo_mode and self.app_env.casefold() in {"development", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
