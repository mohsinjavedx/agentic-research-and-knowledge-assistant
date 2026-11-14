from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, extra="ignore", hide_input_in_errors=True, validate_default=True
    )

    app_env: Literal["development", "test", "production"] = "development"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: SecretStr
    cors_origins: str = "http://localhost:3000"
    embedding_provider: Literal["local", "api"]
    embedding_model: str = Field(min_length=1)
    embedding_dim: int = Field(default=384, ge=384, le=384)
    embedding_api_key: SecretStr = SecretStr("")
    llm_provider: Literal["local", "hosted"]
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    hosted_llm_api_key: SecretStr = SecretStr("")
    hosted_llm_model: str = ""
    enable_reranker: bool = False
    session_ttl_hours: int = Field(default=24, ge=1, le=24)
    max_upload_mb: int = Field(default=20, ge=1, le=20)
    max_pdf_pages: int = Field(default=100, ge=1, le=100)
    rate_limit_chat_per_minute: int = Field(default=5, ge=1)
    rate_limit_research_per_10min: int = Field(default=2, ge=1)
    max_agent_iterations: int = Field(default=4, ge=1, le=4)
    max_tool_calls: int = Field(default=6, ge=1, le=6)
    llm_timeout_seconds: int = Field(default=45, gt=0, le=120)
    db_timeout_seconds: float = Field(default=3, gt=0, le=30)

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: SecretStr) -> SecretStr:
        parsed = urlsplit(value.get_secret_value())
        if (
            parsed.scheme != "postgresql+asyncpg"
            or not parsed.hostname
            or not parsed.path.strip("/")
            or parsed.fragment
        ):
            raise ValueError("must be a postgresql+asyncpg URL with a host and database")
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("database port must be between 1 and 65535")
        return value

    @field_validator("cors_origins")
    @classmethod
    def valid_origins(cls, value: str) -> str:
        for origin in value.split(","):
            parsed = urlsplit(origin.strip())
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
            ):
                raise ValueError("must contain comma-separated HTTP origins without paths")
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @model_validator(mode="after")
    def provider_configuration(self) -> "Settings":
        if self.embedding_provider == "api" and not self.embedding_api_key.get_secret_value():
            raise ValueError("EMBEDDING_API_KEY is required for the API embedding provider")
        if self.llm_provider == "hosted" and (
            not self.hosted_llm_api_key.get_secret_value() or not self.hosted_llm_model.strip()
        ):
            raise ValueError("HOSTED_LLM_API_KEY and HOSTED_LLM_MODEL are required for hosted LLMs")
        if self.app_env == "production" and (
            self.embedding_provider != "api" or self.llm_provider != "hosted"
        ):
            raise ValueError("production requires API embeddings and a hosted LLM")
        return self


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        # Never print Pydantic's input/context: either can contain credentials.
        fields = sorted(
            {
                ".".join(map(str, error["loc"])) or "provider_configuration"
                for error in exc.errors(include_input=False, include_context=False)
            }
        )
        raise RuntimeError(
            "Invalid configuration. Check .env.example; missing or invalid fields: "
            + ", ".join(fields)
        ) from None
