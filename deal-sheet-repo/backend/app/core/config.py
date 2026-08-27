"""Application configuration, loaded from environment variables / a local .env file.

Local dev reads backend/.env (see .env.example). In production (Railway), the
same DATABASE_URL is injected directly as a real environment variable — no
.env file is deployed there.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://dealsheet:dealsheet@localhost:5433/dealsheet"


settings = Settings()
