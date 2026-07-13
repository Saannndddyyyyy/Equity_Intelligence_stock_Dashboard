from pydantic_settings import BaseSettings
from pydantic import Field
from datetime import date
from typing import Optional


class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/equity_db",
        description="Database connection URL",
    )

    # API Keys
    OPENAI_API_KEY: str = Field("", description="OpenAI API Key for Reasoning Engine")
    NEWS_API_KEY: str = Field("", description="NewsAPI Key")
    FINNHUB_API_KEY: str = Field("", description="Finnhub API Key")
    ALPHA_VANTAGE_API_KEY: Optional[str] = Field(
        None, description="Alpha Vantage API Key (fallback)"
    )

    # SMTP Settings
    SMTP_HOST: str = Field("smtp.gmail.com", description="SMTP Server Host")
    SMTP_PORT: int = Field(587, description="SMTP Server Port")
    SMTP_USER: str = Field("", description="SMTP Username")
    SMTP_PASSWORD: str = Field("", description="SMTP Password")
    SMTP_FROM_EMAIL: str = Field("", description="Sender Email Address")
    ALERT_RECEIVER_EMAIL: str = Field("", description="Recipient Email Address")

    # Horizon Rules (9 Months)
    INVESTMENT_START_DATE: date = Field(
        default_factory=date.today,
        description="Start date of the 9-month investment horizon",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
