from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Game Gene Agent API"
    app_version: str = "1.3.0"
    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"
    database_url: str = "sqlite:///./app.db"

    steam_web_api_key: str | None = Field(default=None, repr=False)
    review_author_hash_salt: str | None = Field(default=None, repr=False)
    annotate_uncatalogued_inventory: bool = False
    llm_provider: str = "aliyun_qwen"
    dashscope_api_key: str | None = Field(default=None, repr=False)
    qwen_base_url: str | None = None
    qwen_model: str | None = None
    qwen_timeout_seconds: float = Field(default=180.0, gt=0, le=600)


@lru_cache
def get_settings() -> Settings:
    return Settings()
