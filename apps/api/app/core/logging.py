import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

from app.core.telemetry import telemetry_context

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        telemetry = telemetry_context.get()
        if telemetry is not None:
            payload.update(telemetry.snapshot())
        # Explicit allowlist prevents accidental serialization of credentials or exception text.
        for key in (
            "method",
            "endpoint",
            "status_code",
            "latency_ms",
            "background_ms",
            "session_id",
            "tokens_used",
            "provider",
            "error_code",
            "recovered_documents",
            "scope_ms",
            "embedding_ms",
            "vector_search_ms",
            "generation_ms",
            "total_ms",
            "evidence_count",
            "llm_called",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def configure_logging() -> None:
    # These SDKs can log complete provider errors, prompts or Authorization details.
    # Application code emits fixed events and classified error codes instead.
    namespaces = ("instructor", "openai", "httpx", "httpcore", "pypdf")
    names = set(namespaces) | {
        name
        for name in logging.Logger.manager.loggerDict
        if any(name == prefix or name.startswith(prefix + ".") for prefix in namespaces)
    }
    for name in names:
        dependency = logging.getLogger(name)
        dependency.handlers = [logging.NullHandler()]
        dependency.setLevel(logging.CRITICAL + 1)
        dependency.propagate = False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("research")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
