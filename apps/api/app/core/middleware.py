import logging
from time import perf_counter
from uuid import UUID, uuid4

from starlette._utils import get_route_path
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.identity import private_hash
from app.core.logging import request_id_context
from app.core.telemetry import RequestTelemetry, telemetry_context

logger = logging.getLogger("research.requests")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            request_id = str(UUID(Headers(scope=scope).get("x-request-id", "")))
        except ValueError:
            request_id = str(uuid4())
        token = request_id_context.set(request_id)
        session_hash = None
        try:
            owner = str(UUID(Request(scope).cookies.get("session_id", "")))
            session_hash = private_hash(scope["app"].state.settings, "session", owner)
        except (ValueError, AttributeError, KeyError):
            pass
        telemetry = RequestTelemetry(session_id=session_hash)
        telemetry_token = telemetry_context.set(telemetry)
        started = perf_counter()
        status_code = 500
        response_started = False
        response_elapsed: float | None = None

        async def send_with_id(message: Message) -> None:
            nonlocal status_code, response_started, response_elapsed
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                response_elapsed = (perf_counter() - started) * 1000

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            telemetry.error_code = "INTERNAL_ERROR"
            logger.error("request.failed", extra={"error_code": "INTERNAL_ERROR"})
            if not response_started:
                await JSONResponse(
                    {"detail": "Internal server error", "request_id": request_id}, status_code=500
                )(scope, receive, send_with_id)
        finally:
            # Use route templates, never query strings or arbitrary user-controlled paths.
            route = scope.get("route")
            total_ms = (perf_counter() - started) * 1000
            latency_ms = response_elapsed if response_elapsed is not None else total_ms
            if status_code >= 400 and telemetry.error_code is None:
                telemetry.error_code = {
                    400: "BAD_REQUEST",
                    401: "SESSION_REQUIRED",
                    403: "FORBIDDEN",
                    404: "NOT_FOUND",
                    413: "FILE_TOO_LARGE",
                    415: "UNSUPPORTED_MEDIA_TYPE",
                    422: "INVALID_REQUEST",
                    429: "RATE_LIMIT_EXCEEDED",
                    503: "SERVICE_UNAVAILABLE",
                }.get(status_code, "HTTP_ERROR")
            # Admission can reject before routing. Only match known constant paths.
            from app.core.rate_limits import PROTECTED

            endpoint = getattr(route, "path", None)
            if endpoint is None:
                path = get_route_path(scope).rstrip("/")
                endpoint = path if path in PROTECTED else "unmatched"
            logger.info(
                "request.completed",
                extra={
                    "method": scope["method"],
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "latency_ms": round(latency_ms, 2),
                    "background_ms": round(max(0, total_ms - latency_ms), 2),
                    "total_ms": round(total_ms, 2),
                    **telemetry.snapshot(),
                },
            )
            request_id_context.reset(token)
            telemetry_context.reset(telemetry_token)
