from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DATA_DIR = Path(__file__).parent / "config_data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://matrix:matrix@localhost:5432/matrix"
    cors_origins: str = "http://localhost:5173"

    sec_user_agent: str = "ma3trix-app unset@example.com"

    llm_enabled: bool = False
    llm_api_key: str = ""

    embedding_model: str = "BAAI/bge-small-en-v1.5"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
