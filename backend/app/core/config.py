from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "KAY DEE KAY Manufacturing ERP"
    APP_VERSION: str = "0.1.0"
    TIMEZONE: str = "Asia/Kolkata"

    DATABASE_URL: str = (
        "postgresql+psycopg:///kdk_manufacturing_erp?user=rajat"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
