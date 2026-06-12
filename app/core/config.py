from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "airo-ai"
    DEBUG: bool = False

    DATABASE_URL: str

    WORKER_ENABLED: bool = True
    WORKER_CONCURRENCY: int = 2
    POLL_INTERVAL_SECONDS: float = 2.0
    JOB_TIMEOUT_SECONDS: int = 300
    MAX_JOB_ATTEMPTS: int = 3

    LOG_LEVEL: str = "INFO"

    REDIS_URL: str
    TRANSCRIPT_EVENTS_CHANNEL: str

    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_ENDPOINT_URL: str

    STT_PROVIDER: str = "sarvam"
    SARVAM_API_KEY: str | None = None
    SARVAM_MODEL: str = "saaras:v3"
    SARVAM_MODE: str = "translate"

    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSIONS: int = 384
    HF_TOKEN: str | None = None
    OPENAI_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
