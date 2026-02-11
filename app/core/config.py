from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    OPENAI_API_KEY: str
    
    # Admin Settings
    ADMIN_EMAIL: str = "admin@yourdomain.com"
    ADMIN_NAME: str = "System Admin"
    ADMIN_DEFAULT_PASSWORD: str = "admin123"
    
    # JWT Settings
    JWT_SECRET: str = "your-super-secret-key-change-in-production"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Stripe Settings
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    
    # Payment URLs
    PAYMENT_SUCCESS_URL: str = "https://yourdomain.com/payment/success"
    PAYMENT_CANCEL_URL: str = "https://yourdomain.com/payment/cancel"
    
    # Email Settings
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@example.com"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
