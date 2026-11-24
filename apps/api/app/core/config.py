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
    privacy_hash_key: SecretStr = SecretStr("")
    cors_origins: str = "http://localhost:3000"
    embedding_provider: Literal["local", "api"]
    embedding_model: str = Field(min_length=1)
    embedding_dim: int = Field(default=384, ge=384, le=384)
    embedding_api_key: SecretStr = SecretStr("")
    embedding_api_url: str = ""
    embedding_batch_size: int = Field(default=8, ge=1, le=64)
    embedding_timeout_seconds: float = Field(default=30, gt=0, le=120)
    llm_provider: Literal["local", "hosted"]
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_num_ctx: int = Field(default=2048, ge=512, le=32768)
    hosted_llm_api_key: SecretStr = SecretStr("")
    hosted_llm_model: str = ""
    hosted_llm_base_url: str = "https://api.groq.com/openai/v1"
    hosted_llm_input_token_budget: int = Field(default=6000, ge=512, le=32768)
    enable_reranker: bool = False
    session_ttl_hours: int = Field(default=24, ge=1, le=24)
    max_upload_mb: int = Field(default=20, ge=1, le=20)
    max_pdf_pages: int = Field(default=100, ge=1, le=100)
    retrieval_similarity_threshold: float = Field(default=0.5671493153065035, ge=-1, le=1)
    retrieval_mode: Literal["dense", "hybrid"] = "dense"
    enable_context_expansion: bool = True
    adjacency_similarity_margin: float = Field(default=0.05, ge=0, le=1)
    max_adjacent_chunks: int = Field(default=5, ge=0, le=5)
    min_text_chars_per_page: int = Field(default=50, ge=1, le=10000)
    max_low_text_page_percent: int = Field(default=80, ge=0, le=99)
    chunk_min_tokens: int = Field(default=600, ge=1, le=8000)
    chunk_max_tokens: int = Field(default=800, ge=1, le=8000)
    chunk_overlap_tokens: int = Field(default=100, ge=0, le=7999)
    rate_limit_chat_per_minute: int = Field(default=5, ge=1)
    rate_limit_research_per_10min: int = Field(default=2, ge=1)
    rate_limit_upload_per_hour: int = Field(default=3, ge=1)
    max_agent_iterations: int = Field(default=4, ge=1, le=4)
    max_tool_calls: int = Field(default=6, ge=1, le=6)
    llm_timeout_seconds: int = Field(default=90, gt=0, le=180)
    llm_max_output_tokens: int = Field(default=512, ge=128, le=4096)
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
        if self.app_env == "production" and len(self.privacy_hash_key.get_secret_value()) < 32:
            raise ValueError(
                "production requires a persistent PRIVACY_HASH_KEY of at least32 characters"
            )
        if not self.chunk_overlap_tokens < self.chunk_min_tokens <= self.chunk_max_tokens:
            raise ValueError("chunk budgets require overlap < minimum <= maximum")
        if self.embedding_provider == "api" and not self.embedding_api_key.get_secret_value():
            raise ValueError("EMBEDDING_API_KEY is required for the API embedding provider")
        if self.embedding_provider == "api":
            endpoint = urlsplit(self.embedding_api_url)
            if (
                endpoint.scheme not in {"https", "http"}
                or not endpoint.hostname
                or endpoint.username
                or endpoint.password
                or endpoint.query
                or endpoint.fragment
            ):
                raise ValueError(
                    "EMBEDDING_API_URL must be an HTTP(S) endpoint without credentials"
                )
            if self.app_env == "production" and endpoint.scheme != "https":
                raise ValueError("production embedding API requires HTTPS")
        if self.llm_provider == "hosted" and (
            not self.hosted_llm_api_key.get_secret_value() or not self.hosted_llm_model.strip()
        ):
            raise ValueError("HOSTED_LLM_API_KEY and HOSTED_LLM_MODEL are required for hosted LLMs")
        if self.llm_provider == "local" and self.llm_max_output_tokens >= self.ollama_num_ctx:
            raise ValueError("LLM_MAX_OUTPUT_TOKENS must be less than OLLAMA_NUM_CTX")
        for field_name, base_url in (
            ("ollama_base_url", self.ollama_base_url),
            ("hosted_llm_base_url", self.hosted_llm_base_url),
        ):
            endpoint = urlsplit(base_url)
            if (
                endpoint.scheme not in {"https", "http"}
                or not endpoint.hostname
                or endpoint.username
                or endpoint.password
                or endpoint.query
                or endpoint.fragment
            ):
                raise ValueError(f"{field_name} must be an HTTP(S) URL without credentials")
        if self.app_env == "production" and urlsplit(self.hosted_llm_base_url).scheme != "https":
            raise ValueError("production hosted LLM endpoint requires HTTPS")
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
