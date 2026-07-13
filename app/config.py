from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "LinkPost AI"
    BASE_URL: str = "http://localhost:8000"          # URL pública (Railway) — usada no redirect_uri
    SECRET_KEY: str                                   # Fernet key (gerar: Fernet.generate_key())
    DATABASE_URL: str                                 # postgresql+psycopg://... (Railway)
    REDIS_URL: str = "redis://localhost:6379/0"       # broker/backend Celery (Railway Redis)
    FRONTEND_ORIGINS: str = "http://localhost:5173"   # origens CORS, separadas por vírgula (add URL da Vercel)

    # LinkedIn OAuth (Developer Portal > sua app > Auth)
    LINKEDIN_CLIENT_ID: str
    LINKEDIN_CLIENT_SECRET: str
    LINKEDIN_SCOPES: str = "openid profile w_member_social"
    LINKEDIN_API_VERSION: str = "202606"              # header LinkedIn-Version (YYYYMM) — versões antigas são
                                                      # descontinuadas (sunset); atualizar periodicamente

    # Anthropic
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    # Geração de imagem por IA (opcional) — provedor plugável: "gemini" | "openai"
    IMAGE_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_IMAGE_MODEL: str = "gemini-3.1-flash-image-preview"
    OPENAI_API_KEY: str = ""
    OPENAI_IMAGE_MODEL: str = "gpt-image-1-mini"
    OPENAI_IMAGE_QUALITY: str = "medium"                # low | medium | high

    # Auth (JWT + Google Sign-In)
    JWT_EXPIRE_DAYS: int = 7
    GOOGLE_CLIENT_ID: str = ""                        # OAuth client do Google Cloud (vazio = botão desligado)

    # Stripe (billing)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""       # price_... do plano Starter (R$37)
    STRIPE_PRICE_PRO: str = ""           # price_... do plano Pro (R$87)
    STRIPE_PRICE_AGENCY: str = ""        # price_... do plano Agency (R$257)
    TRIAL_DAYS: int = 5
    FRONTEND_APP_URL: str = "http://localhost:5173"   # p/ redirect pós-checkout

    # Publicação
    PUBLISH_SCAN_INTERVAL_SECONDS: int = 60
    MAX_PUBLISH_ATTEMPTS: int = 3
    TOKEN_REFRESH_MARGIN_DAYS: int = 7                # renova access token quando faltar menos que isso
    STALE_PUBLISHING_MINUTES: int = 15                # posts presos em 'publishing' voltam para a fila
    LINKEDIN_COMMENTARY_MAX_CHARS: int = 3000         # limite do LinkedIn para o campo commentary


@lru_cache
def get_settings() -> Settings:
    return Settings()
