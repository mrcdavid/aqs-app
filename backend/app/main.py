"""FastAPI entry point: `uv run uvicorn app.main:app --reload --port 8000`."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.csrf import CSRFMiddleware
from app.core.headers import SecurityHeadersMiddleware
from app.core.rate_limit import limiter

logger = logging.getLogger("aqs")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        # API docs only outside production.
        docs_url=None if settings.is_production else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/api/openapi.json",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # No CORSMiddleware on purpose: the SPA and API share one origin (Vite proxy in dev).
    # The last middleware added runs first: headers -> CSRF -> OAuth state cookie -> routes.

    # Signed cookie holding only the Google OAuth state/nonce/PKCE verifier, for 10 minutes.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key.get_secret_value(),
        session_cookie=settings.oauth_state_cookie_name,
        max_age=600,
        same_site="lax",
        https_only=settings.secure_cookies,
    )
    app.add_middleware(
        CSRFMiddleware,
        cookie_name=settings.csrf_cookie_name,
        allowed_origin=settings.app_origin,
        secure=settings.secure_cookies,
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        # Safety net for races (e.g. two admins saving the same code); routes pre-check first.
        logger.warning("Integrity error on %s %s: %s", request.method, request.url.path, exc.orig)
        return JSONResponse({"detail": "Conflicts with existing data"}, status_code=409)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    app.include_router(api_router)
    return app


app = create_app()
