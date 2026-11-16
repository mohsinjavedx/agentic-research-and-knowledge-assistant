import os
from pathlib import Path

pytest_plugins = ["tests.conftest_layout"]

# Required on clean checkouts. Real integration runs override DATABASE_URL.
if not (Path(__file__).resolve().parents[3] / ".env").is_file():
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1:55432/test")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
os.environ.setdefault("LLM_PROVIDER", "local")
