import os
from pathlib import Path

import pytest

pytest_plugins = ["tests.conftest_layout"]

# Required on clean checkouts. Real integration runs override DATABASE_URL.
if not (Path(__file__).resolve().parents[3] / ".env").is_file():
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1:55432/test")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
os.environ.setdefault("LLM_PROVIDER", "local")


@pytest.fixture(autouse=True)
def isolate_admission_for_non_quota_tests(request, monkeypatch):
    """Ordinary handler/unit fixtures don't provision a real quota database.

    Rate-limit tests explicitly use the real middleware+PostgreSQL boundary;
    direct quota service tests are never patched by this handler-only stub.
    """
    if request.node.get_closest_marker("rate_limits") is not None:
        return
    from app.core.rate_limits import QuotaDecision

    async def allow_handler_fixture(*args, **kwargs):
        return QuotaDecision(True)

    monkeypatch.setattr("app.core.rate_limits.enforce_quota", allow_handler_fixture)
