from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_name: str = "KnowStack API"
    api_port: int = 8000

    database_url: str
    redis_url: str
    qdrant_url: str

    llm_provider: str = "gemini"
    allow_dev_auth: bool = True
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    default_user_role: str = "user"
    rate_limit_per_minute: int = 60
    qdrant_collection: str = "knowstack_chunks"
    embedding_dim: int = 128
    retrieval_limit: int = 200
    rerank_top_k: int = 5
    job_max_attempts: int = 3
    job_retry_base_seconds: int = 10
    log_level: str = "INFO"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    jwt_issuer: str = ""
    jwt_audience: str = ""
    jwt_jwks_url: str = ""
    max_upload_mb: int = 25
    local_upload_dir: str = "./uploaded_files"


settings = Settings()
