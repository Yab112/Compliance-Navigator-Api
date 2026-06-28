from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    neo4j_uri: str = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username: str = os.environ.get("NEO4J_USERNAME")
    neo4j_password: str = os.environ.get("NEO4J_PASSWORD", "darixsamani")
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

    supabase_url: str | None = os.environ.get("SUPABASE_URL")
    supabase_service_role_key: str | None = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase_anon_key: str | None = os.environ.get("SUPABASE_ANON_KEY")
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
    llm_provider: str = os.environ.get("LLM_PROVIDER", "ollama")
    ollama_base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.environ.get("OLLAMA_MODEL", "llama3.2")
    hf_token: str | None = os.environ.get("HF_TOKEN")
    whisper_model_size: str = os.environ.get("WHISPER_MODEL_SIZE", "small")
    supabase_storage_bucket: str = os.environ.get(
        "SUPABASE_STORAGE_BUCKET", "compliance-uploads"
    )

    aws_access_key_id: str | None = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = os.environ.get("AWS_SECRET_ACCESS_KEY")
    aws_region: str = os.environ.get("AWS_REGION", "us-east-1")
    s3_bucket: str | None = os.environ.get("S3_BUCKET")
    s3_endpoint_url: str | None = os.environ.get("S3_ENDPOINT_URL")
    s3_public_base_url: str | None = os.environ.get("S3_PUBLIC_BASE_URL")

    qdrant_host: str = os.environ.get("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.environ.get("QDRANT_PORT", "6333"))
    minio_endpoint: str = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket: str = os.environ.get("MINIO_BUCKET", "compliance-uploads")
    upload_dir: str = os.environ.get("UPLOAD_DIR", "uploads/references")

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


settings = Settings()