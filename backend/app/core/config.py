from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "AI-MemoryVerse"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "insecure-dev-secret-key-change-in-production-min-32-chars"
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    CORS_ALLOWED_ORIGINS: list[str] | str = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost",
        "https://127.0.0.1",
        "http://localhost",
        "http://127.0.0.1",
        "https://memoryverse.local",
        "http://memoryverse.local",
    ]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/memoryverse"
    DATABASE_SYNC_URL: str = (
        "postgresql+psycopg2://postgres:postgrespassword@localhost:5432/memoryverse"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # AI Configuration
    LLM_PROVIDER: str = "mock"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    VISION_PROVIDER: str = "mock"
    SPEECH_PROVIDER: str = "mock"
    OPENAI_WHISPER_MODEL: str = "whisper-1"
    OPENAI_TTS_MODEL: str = "tts-1"

    # Storage
    STORAGE_PROVIDER: str = "local"
    STORAGE_ENDPOINT: str = ""
    STORAGE_BUCKET: str = "memoryverse-documents"
    STORAGE_REGION: str = "us-east-1"
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""
    LOCAL_STORAGE_PATH: str = "./storage/uploads"

    # Authentication & Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOW_DEMO_LOGIN: bool = False
    RATE_LIMIT_ENABLED: bool = True
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: str = ""

    # Billing
    PAYMENT_PROVIDER: str = "sandbox"
    PAYMENT_SECRET_KEY: str = ""
    PAYMENT_WEBHOOK_SECRET: str = ""

    # Account Lockout & Security Bounds
    ACCOUNT_LOCKOUT_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    # Storage Quotas by Plan Tier (in bytes)
    STORAGE_QUOTA_BYTES_BY_TIER: dict[str, int] = {
        "free": 500 * 1024 * 1024,
        "pro": 10 * 1024 * 1024 * 1024,
        "enterprise": 100 * 1024 * 1024 * 1024,
    }

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        if info.data.get("APP_ENV") == "production" and (
            not v or "insecure-dev-secret-key" in v or len(v) < 32
        ):
            raise ValueError(
                "SECRET_KEY must be a secure, cryptographically random key of at least 32 characters in production."
            )
        return v

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]


settings = Settings()
