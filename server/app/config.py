import os

from pydantic_settings import BaseSettings


def _derive_sync_url(async_url: str) -> str:
    """Convert asyncpg URL to psycopg2 URL."""
    return async_url.replace("+asyncpg", "").replace("postgresql://", "postgresql://", 1)


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://neuralfight:neuralfight@localhost:5432/neuralfight"
    database_url_sync: str = ""
    the_odds_api_key: str = ""
    allowed_origins: str = "http://localhost:5173"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Railway provides DATABASE_URL as a plain postgres:// URL
        raw = os.environ.get("DATABASE_URL", "")
        if raw:
            # Ensure async URL uses asyncpg
            if "+asyncpg" not in self.database_url and "asyncpg" not in self.database_url:
                self.database_url = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
            if not self.database_url_sync:
                self.database_url_sync = _derive_sync_url(self.database_url)
        if not self.database_url_sync:
            self.database_url_sync = _derive_sync_url(self.database_url)

    model_config = {"env_file": ["../.env", ".env"], "env_file_encoding": "utf-8"}


settings = Settings()
