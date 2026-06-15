from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "./uploads"
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me"

    # Telegram Bot (optional — leave blank to disable Telegram ingestion)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""  # Secret token to verify Telegram requests

    class Config:
        env_file = ".env"


settings = Settings()
