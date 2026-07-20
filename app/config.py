from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "Posthink"
    BASE_URL: str = "https://api.posthink.com.br"     # URL pública da API — usada no redirect_uri do LinkedIn
    SECRET_KEY: str                                   # Fernet key (gerar: Fernet.generate_key())
    DATABASE_URL: str                                 # postgresql+psycopg://... (Railway)
    REDIS_URL: str = "redis://localhost:6379/0"       # broker/backend Celery (Railway Redis)
    FRONTEND_ORIGINS: str = "https://posthink.com.br" # origens CORS, separadas por vírgula

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
    GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"
    OPENAI_API_KEY: str = ""
    OPENAI_IMAGE_MODEL: str = "gpt-image-1-mini"
    OPENAI_IMAGE_QUALITY: str = "medium"                # low | medium | high

    # Auth (JWT + Google Sign-In)
    JWT_EXPIRE_DAYS: int = 7
    GOOGLE_CLIENT_ID: str = ""                        # OAuth client do Google Cloud (vazio = botão desligado)

    # Stripe (billing)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""       # price_... do plano Starter (R$20)
    STRIPE_PRICE_PRO: str = ""           # price_... do plano Pro (R$45,70)
    STRIPE_PRICE_AGENCY: str = ""        # price_... do plano Agency (R$100 mensal)
    STRIPE_PRICE_STARTER_ANNUAL: str = ""   # price_... anual
    STRIPE_PRICE_PRO_ANNUAL: str = ""
    STRIPE_PRICE_AGENCY_ANNUAL: str = ""
    GUARANTEE_DAYS: int = 7                           # garantia de devolução (CDC art.49: mínimo 7)
    FRONTEND_APP_URL: str = "https://posthink.com.br" # p/ redirect pós-checkout do Stripe

    # Publicação
    PUBLISH_SCAN_INTERVAL_SECONDS: int = 60
    MAX_PUBLISH_ATTEMPTS: int = 3
    TOKEN_REFRESH_MARGIN_DAYS: int = 7                # renova access token quando faltar menos que isso
    STALE_PUBLISHING_MINUTES: int = 15                # posts presos em 'publishing' voltam para a fila
    LINKEDIN_COMMENTARY_MAX_CHARS: int = 3000         # limite do LinkedIn para o campo commentary


@lru_cache
def get_settings() -> Settings:
    return Settings()
