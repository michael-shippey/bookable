from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, loaded from environment variables (or a .env file)."""

    database_url: str = "postgresql+psycopg://bookable:bookable@localhost:5432/bookable"
    app_name: str = "Bookable"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
