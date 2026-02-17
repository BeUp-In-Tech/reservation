from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str

    # JWT
    JWT_SECRET: str
    JWT_EXPIRATION_HOURS: int = 24
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Admin
    ADMIN_EMAIL: str
    ADMIN_NAME: str = "System Admin"
    ADMIN_DEFAULT_PASSWORD: str

    # Optional keys
    OPENAI_API_KEY: str | None = None

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    PAYMENT_SUCCESS_URL: str = "https://yourdomain.com/payment/success"
    PAYMENT_CANCEL_URL: str = "https://yourdomain.com/payment/cancel"

    # Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@example.com"
    RESEND_API_KEY: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
