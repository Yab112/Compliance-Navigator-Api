from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from urllib.parse import urlsplit

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    neo4j_uri: str = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username: str = os.environ.get("NEO4J_USERNAME")
    # No default: set it in .env (docker compose uses the same value)
    neo4j_password: str | None = os.environ.get("NEO4J_PASSWORD")
    redis_host: str = os.environ.get("REDIS_HOST", "localhost")
    redis_port: str = os.environ.get("REDIS_PORT", "6379")
    celery_broker_url: str | None = os.environ.get("CELERY_BROKER_URL")
    celery_result_backend: str | None = os.environ.get("CELERY_RESULT_BACKEND")

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or f"{self.redis_url}/0"

    @property
    def result_backend_url(self) -> str:
        return self.celery_result_backend or f"{self.redis_url}/1"




    secret_key: str = os.environ.get("SECRET_KEY", "change-me-in-production")
    algorithm: str = "HS256"

    # Postgres system of record
    database_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql://navigator:navigator@localhost:5433/compliance_navigator",
    )
    # Auth: short-lived JWT access tokens + rotating refresh tokens in an httpOnly cookie
    access_token_ttl_minutes: int = int(os.environ.get("ACCESS_TOKEN_TTL_MINUTES", "15"))
    refresh_token_ttl_days: int = int(os.environ.get("REFRESH_TOKEN_TTL_DAYS", "30"))
    auth_cookie_secure: bool = os.environ.get("AUTH_COOKIE_SECURE", "false").lower() == "true"
    # "lax" when web and API share a site; "none" (requires secure) for cross-site deployments
    auth_cookie_samesite: str = os.environ.get("AUTH_COOKIE_SAMESITE", "lax")
    # Public web origin, used to build password-reset links
    web_base_url: str = os.environ.get("WEB_BASE_URL", "http://localhost:3000")
    # Staff (admin app) origin, used to build staff invitation and password links
    admin_base_url: str = os.environ.get("ADMIN_BASE_URL", "http://localhost:3001")
    # Optional SMTP for password-reset email; without it links are logged and admins can issue them
    smtp_host: str | None = os.environ.get("SMTP_HOST")
    smtp_port: int = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username: str | None = os.environ.get("SMTP_USERNAME")
    smtp_password: str | None = os.environ.get("SMTP_PASSWORD")
    smtp_from: str = os.environ.get("SMTP_FROM", "no-reply@localhost")
    environment: str = os.environ.get("ENVIRONMENT", "development")
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")
    # Shared password of the seeded demo accounts; never set in production
    demo_password: str | None = os.environ.get("DEMO_PASSWORD")
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
    llm_provider: str = os.environ.get("LLM_PROVIDER", "ollama")
    ollama_base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.environ.get("OLLAMA_MODEL", "llama3.2")
    hf_token: str | None = os.environ.get("HF_TOKEN")
    whisper_model_size: str = os.environ.get("WHISPER_MODEL_SIZE", "small")

    aws_access_key_id: str | None = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = os.environ.get("AWS_SECRET_ACCESS_KEY")
    aws_region: str = os.environ.get("AWS_REGION", "us-east-1")
    s3_bucket: str | None = os.environ.get("S3_BUCKET")
    s3_endpoint_url: str | None = os.environ.get("S3_ENDPOINT_URL")
    s3_public_base_url: str | None = os.environ.get("S3_PUBLIC_BASE_URL")

    qdrant_host: str = os.environ.get("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.environ.get("QDRANT_PORT", "6333"))
    minio_endpoint: str = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str | None = os.environ.get("MINIO_ACCESS_KEY")
    minio_secret_key: str | None = os.environ.get("MINIO_SECRET_KEY")
    minio_bucket: str = os.environ.get("MINIO_BUCKET", "compliance-uploads")
    upload_dir: str = os.environ.get("UPLOAD_DIR", "uploads/references")

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"

    # Fayda national ID verification (MOSIP eSignet). off | sandbox | live
    fayda_mode: str = os.environ.get("FAYDA_MODE", "sandbox")
    fayda_client_id: str | None = os.environ.get("FAYDA_CLIENT_ID")
    fayda_authorize_url: str | None = os.environ.get("FAYDA_AUTHORIZE_URL")
    fayda_token_url: str | None = os.environ.get("FAYDA_TOKEN_URL")
    fayda_userinfo_url: str | None = os.environ.get("FAYDA_USERINFO_URL")
    fayda_jwks_url: str | None = os.environ.get("FAYDA_JWKS_URL")
    # Expected "iss" of Fayda tokens (the eSignet base URL); checked when set
    fayda_issuer: str | None = os.environ.get("FAYDA_ISSUER")
    fayda_private_key: str | None = os.environ.get("FAYDA_PRIVATE_KEY")  # PEM text or file path
    fayda_redirect_uri: str = os.environ.get(
        "FAYDA_REDIRECT_URI", "http://localhost:3000/guday/register/fayda-callback"
    )
    fayda_sandbox_url: str = os.environ.get(
        "FAYDA_SANDBOX_URL", "http://localhost:3000/guday/register/fayda-sandbox"
    )
    # Keys the national ID hash; defaults to SECRET_KEY, set it once and never change it
    id_hash_pepper: str | None = os.environ.get("ID_HASH_PEPPER")

    # Paying providers through the platform. off | simulated (local checkout, no money) | chapa
    payments_mode: str = os.environ.get("PAYMENTS_MODE", "simulated")
    chapa_secret_key: str | None = os.environ.get("CHAPA_SECRET_KEY")  # CHASECK_TEST-... while testing
    chapa_webhook_secret: str | None = os.environ.get("CHAPA_WEBHOOK_SECRET")
    chapa_base_url: str = os.environ.get("CHAPA_BASE_URL", "https://api.chapa.co/v1")
    # Our share of every payment, in percent; the rest is split to the provider by the gateway
    platform_commission_percent: float = float(os.environ.get("PLATFORM_COMMISSION_PERCENT", "10"))
    # VAT (Proclamation 1341/2024). The standard rate is 15%; set by an accountant, not hard-coded in logic
    vat_rate_percent: float = float(os.environ.get("VAT_RATE_PERCENT", "15"))
    # Whether we are VAT-registered: then VAT is charged on our commission
    platform_vat_registered: bool = os.environ.get("PLATFORM_VAT_REGISTERED", "true").lower() == "true"
    # Shown on receipts
    platform_legal_name: str = os.environ.get("PLATFORM_LEGAL_NAME", "Compliance Navigator")
    platform_tin: str | None = os.environ.get("PLATFORM_TIN")
    platform_vat_number: str | None = os.environ.get("PLATFORM_VAT_NUMBER")
    platform_address: str = os.environ.get("PLATFORM_ADDRESS", "Addis Ababa, Ethiopia")
    # Public address of this API, for gateway callbacks (a tunnel URL when testing webhooks locally)
    api_public_url: str = os.environ.get("API_PUBLIC_URL", "http://localhost:8080")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return (self.environment or "").strip().lower() == "production"

    def production_problems(self) -> list[str]:
        """Everything that makes this configuration unsafe to run in production (empty when fine)."""
        if not self.is_production:
            return []
        problems: list[str] = []
        key = self.secret_key or ""
        if key.startswith("change-me") or len(key) < 32:
            problems.append("SECRET_KEY must be at least 32 random characters (not the change-me default)")
        if not self.neo4j_password or self.neo4j_password == "darixsamani" or self.neo4j_password.startswith("change-me"):
            problems.append("NEO4J_PASSWORD must be set to a real password")
        if "minioadmin" in (self.minio_access_key, self.minio_secret_key):
            problems.append("MINIO_ACCESS_KEY and MINIO_SECRET_KEY must not be minioadmin")
        if "navigator:navigator@" in self.database_url or "change-me" in self.database_url:
            problems.append("DATABASE_URL still uses a default password")
        if not self.auth_cookie_secure:
            problems.append("AUTH_COOKIE_SECURE must be true")
        for origin in self.cors_origin_list:
            if origin == "*" or "localhost" in origin or "127.0.0.1" in origin or origin.startswith("http://"):
                problems.append(f"CORS_ORIGINS must list only https sites of this service (found {origin})")
        for name in ("web_base_url", "admin_base_url", "api_public_url"):
            if urlsplit(getattr(self, name) or "").scheme != "https":
                problems.append(f"{name.upper()} must be an https:// address")
        if self.payments_mode != "chapa":
            problems.append("PAYMENTS_MODE must be chapa")
        if not self.chapa_secret_key or self.chapa_secret_key.startswith("CHASECK_TEST-"):
            problems.append("CHAPA_SECRET_KEY must be the live key (not empty, not CHASECK_TEST-)")
        if not self.chapa_webhook_secret:
            problems.append("CHAPA_WEBHOOK_SECRET must be set")
        if (self.fayda_mode or "").lower() != "live":
            problems.append("FAYDA_MODE must be live (sandbox accepts made-up IDs)")
        fayda_missing = [name for name, value in {
            "FAYDA_CLIENT_ID": self.fayda_client_id, "FAYDA_AUTHORIZE_URL": self.fayda_authorize_url,
            "FAYDA_TOKEN_URL": self.fayda_token_url, "FAYDA_USERINFO_URL": self.fayda_userinfo_url,
            "FAYDA_JWKS_URL": self.fayda_jwks_url, "FAYDA_PRIVATE_KEY": self.fayda_private_key,
        }.items() if not value]
        if fayda_missing:
            problems.append(f"Fayda live settings missing: {', '.join(fayda_missing)}")
        if urlsplit(self.fayda_redirect_uri or "").scheme != "https":
            problems.append("FAYDA_REDIRECT_URI must be an https:// address")
        if not self.id_hash_pepper:
            problems.append("ID_HASH_PEPPER must be set (once, never changed)")
        if not self.smtp_host:
            problems.append("SMTP_HOST must be set (sign-up and password emails need it)")
        if (self.log_level or "").strip().upper() == "DEBUG":
            problems.append("LOG_LEVEL must not be DEBUG")
        if self.demo_password:
            problems.append("DEMO_PASSWORD must not be set")
        return problems

    def check_production(self) -> None:
        problems = self.production_problems()
        if problems:
            raise RuntimeError(
                "Refusing to start with ENVIRONMENT=production. Fix these settings:\n- " + "\n- ".join(problems)
            )


settings = Settings()
# Development stays permissive; production stops here with one message listing every problem
settings.check_production()