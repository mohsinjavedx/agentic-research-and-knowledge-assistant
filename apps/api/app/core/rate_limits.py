"""Atomic PostgreSQL admission before reading protected request bodies."""

import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta
from math import ceil
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from starlette._utils import get_route_path
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.v1.sessions import require_session_id
from app.core.identity import RequestIdentity, request_identity
from app.db.errors import DATABASE_ERRORS
from app.db.models import RateLimitEvent
from app.db.session import Database

Action = Literal["chat", "research", "upload"]
PROTECTED: dict[str, Action] = {
    "/api/v1/answer": "chat",
    "/api/v1/search": "chat",
    "/api/v1/research": "research",
    "/api/v1/documents": "upload",
}
logger = logging.getLogger("research.admission")


@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    retry_after: int = 0


async def consume_quota(
    database: Database,
    identity: RequestIdentity,
    action: Action,
    *,
    limit: int,
    window_seconds: int,
) -> QuotaDecision:
    if limit < 1 or not 1 <= window_seconds <= 3600:
        raise ValueError("Invalid sliding-window quota.")
    keys = sorted(
        {
            int.from_bytes(
                hashlib.sha256(f"quota:{action}:{kind}:{value}".encode()).digest()[:8],
                "big",
                signed=True,
            )
            for kind, value in (("ip", identity.ip_hash), ("session", identity.session_hash))
        }
    )
    async with database.sessions() as session, session.begin():
        for key in keys:
            await session.execute(select(func.pg_advisory_xact_lock(key)))
        now = await session.scalar(select(func.clock_timestamp()))
        assert now is not None
        window = timedelta(seconds=window_seconds)
        rows = (
            await session.execute(
                select(
                    RateLimitEvent.created_at, RateLimitEvent.ip_hash, RateLimitEvent.session_hash
                )
                .where(
                    RateLimitEvent.action == action,
                    RateLimitEvent.created_at > now - window,
                    or_(
                        RateLimitEvent.ip_hash == identity.ip_hash,
                        RateLimitEvent.session_hash == identity.session_hash,
                    ),
                )
                .order_by(RateLimitEvent.created_at)
            )
        ).all()
        blocked_until = []
        for column, value in (
            ("ip_hash", identity.ip_hash),
            ("session_hash", identity.session_hash),
        ):
            matching = [row.created_at for row in rows if getattr(row, column) == value]
            if len(matching) >= limit:
                blocked_until.append(matching[-limit] + window)
        if blocked_until:
            return QuotaDecision(False, max(1, ceil((max(blocked_until) - now).total_seconds())))
        session.add(
            RateLimitEvent(
                action=action,
                ip_hash=identity.ip_hash,
                session_hash=identity.session_hash,
                created_at=now,
            )
        )
    return QuotaDecision(True)


async def enforce_quota(request: Request, action: Action) -> QuotaDecision:
    owner = require_session_id(request)
    settings = request.app.state.settings
    identity = request_identity(
        settings, request.client.host if request.client else "unknown", owner
    )
    count, seconds = {
        "chat": (settings.rate_limit_chat_per_minute, 60),
        "research": (settings.rate_limit_research_per_10min, 600),
        "upload": (settings.rate_limit_upload_per_hour, 3600),
    }[action]
    return await consume_quota(
        request.app.state.database, identity, action, limit=count, window_seconds=seconds
    )


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        action = (
            PROTECTED.get(get_route_path(scope).rstrip("/")) if scope["type"] == "http" else None
        )
        if scope["type"] != "http" or scope.get("method") != "POST" or action is None:
            await self.app(scope, receive, send)
            return
        try:
            decision = await enforce_quota(Request(scope), action)
        except HTTPException as exc:
            await JSONResponse({"detail": exc.detail}, status_code=exc.status_code)(
                scope, receive, send
            )
            return
        except DATABASE_ERRORS:
            logger.error("quota.database_failed", extra={"error_code": "RATE_LIMIT_UNAVAILABLE"})
            await JSONResponse(
                {"detail": "Request admission is temporarily unavailable. Try again."},
                status_code=503,
                headers={"Retry-After": "5"},
            )(scope, receive, send)
            return
        if not decision.allowed:
            logger.warning("quota.exceeded", extra={"error_code": "RATE_LIMIT_EXCEEDED"})
            await JSONResponse(
                {
                    "detail": "The request limit was reached. Try again after the indicated wait.",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                },
                status_code=429,
                headers={"Retry-After": str(decision.retry_after), "Cache-Control": "no-store"},
            )(scope, receive, send)
            return
        await self.app(scope, receive, send)
