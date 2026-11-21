import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        # Explicit allowlist prevents accidental serialization of credentials or exception text.
        for key in (
            "method",
            "endpoint",
            "status_code",
            "latency_ms",
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
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("research")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
