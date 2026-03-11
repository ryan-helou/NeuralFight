from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://neuralfight:neuralfight@localhost:5432/neuralfight"
    database_url_sync: str = "postgresql://neuralfight:neuralfight@localhost:5432/neuralfight"
    the_odds_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
