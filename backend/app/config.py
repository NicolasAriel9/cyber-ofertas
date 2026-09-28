from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    basic_auth_user: str = "nico"
    basic_auth_password: str = "changeme"
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    default_drop_alert_threshold_pct: float = 5.0


settings = Settings()
