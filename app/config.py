"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the grievance chatbot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Multilingual Citizen Grievance Chatbot", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secret_key: str = Field(default="change-me", alias="SECRET_KEY")
    database_url: str = Field(default="sqlite:///./grievance.db", alias="DATABASE_URL")
    cors_origins: str = Field(
        default="http://127.0.0.1:8000,http://localhost:8000",
        alias="CORS_ORIGINS",
    )
    allowed_hosts: str = Field(default="127.0.0.1,localhost", alias="ALLOWED_HOSTS")
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str | None = Field(default=None, alias="ADMIN_PASSWORD")
    classification_confidence_threshold: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        alias="CLASSIFICATION_CONFIDENCE_THRESHOLD",
    )
    demo_sla_minutes: int = Field(default=2, gt=0, alias="DEMO_SLA_MINUTES")
    escalation_interval_minutes: int = Field(default=5, gt=0, alias="ESCALATION_INTERVAL_MINUTES")
    enable_voice: bool = Field(default=False, alias="ENABLE_VOICE")
    whisper_model: str = Field(default="small", alias="WHISPER_MODEL")
    max_voice_upload_mb: int = Field(default=10, gt=0, le=50, alias="MAX_VOICE_UPLOAD_MB")
    max_request_body_mb: int = Field(default=12, gt=0, le=50, alias="MAX_REQUEST_BODY_MB")
    enable_ai_routing: bool = Field(default=False, alias="ENABLE_AI_ROUTING")
    sarvam_api_key: str | None = Field(default=None, alias="SARVAM_API_KEY")
    sarvam_model: str = Field(default="sarvam-105b", alias="SARVAM_MODEL")
    sarvam_api_url: str = Field(
        default="https://api.sarvam.ai/v1/chat/completions",
        alias="SARVAM_API_URL",
    )
    ai_routing_timeout_seconds: float = Field(
        default=12.0,
        gt=0,
        le=60,
        alias="AI_ROUTING_TIMEOUT_SECONDS",
    )
    enable_translation: bool = Field(default=False, alias="ENABLE_TRANSLATION")
    translation_external_fallback: bool = Field(default=False, alias="TRANSLATION_EXTERNAL_FALLBACK")
    enable_langchain: bool = Field(default=False, alias="ENABLE_LANGCHAIN")
    enable_ml_classifier: bool = Field(default=True, alias="ENABLE_ML_CLASSIFIER")
    classifier_model_path: str = Field(default="ml/models/classifier.joblib", alias="CLASSIFIER_MODEL_PATH")
    model_dir: str = Field(default="ml/models", alias="MODEL_DIR")
    embedding_model: str = Field(default="intfloat/multilingual-e5-small", alias="EMBEDDING_MODEL")
    translation_model: str = Field(default="ai4bharat/indictrans2-indic-en-dist-200M", alias="TRANSLATION_MODEL")

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        """Prevent an unsafe default configuration in production."""

        if self.app_env.lower() in {"production", "prod"}:
            if self.debug:
                raise ValueError("DEBUG must be false in production")
            if self.secret_key == "change-me":
                raise ValueError("SECRET_KEY must be replaced in production")
            if not self.admin_password:
                raise ValueError("ADMIN_PASSWORD must be configured in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        """Return configured CORS origins as a cleaned list."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        """Return configured hosts as a cleaned list."""

        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
