from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, loaded from environment variables (or a .env file)."""

    database_url: str = "postgresql+psycopg://bookable:bookable@localhost:5432/bookable"
    app_name: str = "Bookable"

    # No default on purpose: the app refuses to start without a secret key,
    # so a weak key can never be used by accident in production.
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Customers must cancel at least this long before the start. Business
    # owners and admins can cancel at any time before it starts.
    cancellation_notice_hours: int = 24

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
