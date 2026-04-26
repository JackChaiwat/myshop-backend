from pydantic_settings import BaseSettings
from typing import List
from pydantic import field_validator
import json


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Online Shop"
    DEBUG: bool = False
    SECRET_KEY: str

    # Database
    DATABASE_URL: str

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # CORS — default ใช้ได้แค่ local dev
    # production: ต้องตั้ง ALLOWED_ORIGINS และ ALLOWED_HOSTS ใน Render dashboard เสมอ
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ]
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

    # Payment
    LEMONSQUEEZY_API_KEY: str = ""
    LEMONSQUEEZY_STORE_ID: str = ""
    LEMONSQUEEZY_WEBHOOK_SECRET: str = ""
    OMISE_PUBLIC_KEY: str = ""
    OMISE_SECRET_KEY: str = ""
    OMISE_WEBHOOK_SECRET: str = ""

    # Email
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "onboarding@resend.dev"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "shop-assets"
    R2_PUBLIC_URL: str = ""

    # Meilisearch
    MEILISEARCH_URL: str = "http://meilisearch:7700"
    MEILISEARCH_API_KEY: str = "masterkey"

    # Optional services
    POSTHOG_API_KEY: str = ""
    SENTRY_DSN: str = ""
    GEMINI_API_KEY: str = ""
    N8N_WEBHOOK_URL: str = ""

    # ─── Validators ───────────────────────────────────────────────────────────

    @field_validator("ALLOWED_ORIGINS", "ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_list_env(cls, v):
        """
        Render ส่ง env var เป็น string เสมอ รองรับทั้ง 2 รูปแบบ:
          ["https://myshop-frontend-nn8g.onrender.com","http://localhost:5173"]
          https://myshop-frontend-nn8g.onrender.com,http://localhost:5173
        """
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def jwt_secret_must_differ(cls, v: str, info) -> str:
        secret_key = info.data.get("SECRET_KEY", "")
        if secret_key and v == secret_key:
            raise ValueError(
                "JWT_SECRET must be different from SECRET_KEY. "
                'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return v

    @field_validator("ALLOWED_HOSTS")
    @classmethod
    def no_wildcard_in_production(cls, v: List[str], info) -> List[str]:
        debug = info.data.get("DEBUG", False)
        if not debug and "*" in v:
            raise ValueError(
                'ALLOWED_HOSTS=["*"] is not allowed when DEBUG=false. '
                "Set your actual domain(s) instead."
            )
        return v

    class Config:
        env_file = ".env"


settings = Settings()
