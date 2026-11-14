import logging
from time import perf_counter
from uuid import UUID, uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_context

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
        started = perf_counter()
        status_code = 500
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            logger.error("request.failed", extra={"error_code": "INTERNAL_ERROR"})
            if response_started:
                raise
            await JSONResponse(
                {"detail": "Internal server error", "request_id": request_id}, status_code=500
            )(scope, receive, send_with_id)
        finally:
            # Use route templates, never query strings or arbitrary user-controlled paths.
            route = scope.get("route")
            logger.info(
                "request.completed",
                extra={
                    "method": scope["method"],
                    "endpoint": getattr(route, "path", "unmatched"),
                    "status_code": status_code,
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            request_id_context.reset(token)
