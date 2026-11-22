"""Anonymous browser-session cookie management."""

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.config import Settings

SESSION_COOKIE_NAME = "session_id"
router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.post("/session", status_code=status.HTTP_204_NO_CONTENT)
async def create_session(request: Request, response: Response) -> Response:
    settings: Settings = request.app.state.settings
    existing_session = request.cookies.get(SESSION_COOKIE_NAME)
    if existing_session is not None:
        try:
            UUID(existing_session)
            response.status_code = status.HTTP_204_NO_CONTENT
            response.headers["Cache-Control"] = "no-store"
            return response
        except ValueError:
            pass
    response.status_code = status.HTTP_204_NO_CONTENT
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=str(uuid4()),
        max_age=settings.session_ttl_hours * 60 * 60,
        path="/api/v1",
        secure=settings.app_env == "production",
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Cache-Control"] = "no-store"
    return response


def require_session_id(request: Request) -> UUID:
    value = request.cookies.get(SESSION_COOKIE_NAME)
    if value is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session required.")
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session."
        ) from None
