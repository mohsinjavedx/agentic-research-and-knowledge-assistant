import pytest
from pydantic import ValidationError

from app.core.config import Settings, load_settings


def values(**overrides: object) -> dict[str, object]:
    return {
        "database_url": "postgresql+asyncpg://user:secret@localhost/research",
        "embedding_provider": "local",
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "llm_provider": "local",
        **overrides,
    }


def test_local_configuration() -> None:
    settings = Settings(_env_file=None, **values())
    assert settings.embedding_dim == 384
    assert settings.allowed_origins == ["http://localhost:3000"]
    assert "secret" not in repr(settings)


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": "sqlite:///data.db"},
        {"embedding_dim": 768},
        {"max_agent_iterations": 5},
        {"cors_origins": "*"},
        {"cors_origins": "http://localhost:3000/path"},
        {"app_env": "production"},
        {"llm_provider": "hosted", "hosted_llm_api_key": "", "hosted_llm_model": ""},
        {"embedding_provider": "api", "embedding_api_key": ""},
    ],
)
def test_invalid_configuration(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values(**overrides))


def test_startup_missing_settings_has_clear_sanitized_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in ("DATABASE_URL", "EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "LLM_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="database_url") as caught:
        load_settings()
    assert "embedding_model" in str(caught.value)
    assert "Check .env.example" in str(caught.value)


def test_invalid_secret_is_not_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("DATABASE_URL", "invalid://user:DO_NOT_LOG_ME@host/db")
    with pytest.raises(RuntimeError) as caught:
        load_settings()
    assert "DO_NOT_LOG_ME" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_production_provider_configuration() -> None:
    settings = Settings(
        _env_file=None,
        **values(
            app_env="production",
            embedding_provider="api",
            embedding_api_key="test-embedding-key",
            llm_provider="hosted",
            hosted_llm_api_key="test-llm-key",
            hosted_llm_model="example-model",
        ),
    )
    assert settings.app_env == "production"
