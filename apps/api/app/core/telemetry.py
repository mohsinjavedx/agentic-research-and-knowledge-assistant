"""Request-local accounting shared with copied worker contexts; no input text."""

from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ProviderCall:
    provider: str
    tokens: int | None = None
    _lock: Lock = field(default_factory=Lock, repr=False)

    def complete(self, tokens: object) -> None:
        with self._lock:
            self.tokens = tokens if type(tokens) is int and tokens >= 0 else None

    def count(self) -> int | None:
        with self._lock:
            return self.tokens


@dataclass
class RequestTelemetry:
    session_id: str | None
    error_code: str | None = None
    _calls: list[ProviderCall] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def add_call(self, call: ProviderCall) -> None:
        with self._lock:
            self._calls.append(call)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            calls = tuple(self._calls)
        counts = [call.count() for call in calls]
        return {
            "session_id": self.session_id,
            "tokens_used": None if None in counts else sum(n for n in counts if n is not None),
            "provider": ",".join(sorted({call.provider for call in calls})) or "none",
            "error_code": self.error_code,
        }


telemetry_context: ContextVar[RequestTelemetry | None] = ContextVar("telemetry", default=None)


def begin_provider_call(provider: str) -> ProviderCall:
    if provider not in {"local", "hosted", "api"}:
        raise ValueError("Unknown telemetry provider")
    call = ProviderCall(provider)
    telemetry = telemetry_context.get()
    if telemetry is not None:
        telemetry.add_call(call)
    return call


def set_error_code(code: str) -> None:
    telemetry = telemetry_context.get()
    if telemetry is not None:
        telemetry.error_code = code
