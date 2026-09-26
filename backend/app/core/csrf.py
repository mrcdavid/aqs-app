"""CSRF protection: Origin check + double-submit token for state-changing requests.

The server sets a JS-readable `aqs_csrf` cookie; the frontend echoes it in the
`X-CSRF-Token` header. A cross-site attacker cannot read the cookie, so cannot forge the header.
"""

import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
HEADER_NAME = "X-CSRF-Token"


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(  # noqa: ANN001
        self, app, *, cookie_name: str, allowed_origin: str, secure: bool, exempt_paths=()
    ) -> None:
        super().__init__(app)
        self.cookie_name = cookie_name
        self.allowed_origin = allowed_origin
        self.secure = secure
        self.exempt_paths = set(exempt_paths)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in SAFE_METHODS and request.url.path not in self.exempt_paths:
            origin = request.headers.get("origin")
            if origin is not None and origin != self.allowed_origin:
                return JSONResponse({"detail": "Bad origin"}, status_code=403)

            cookie = request.cookies.get(self.cookie_name)
            header = request.headers.get(HEADER_NAME)
            if not cookie or not header or not secrets.compare_digest(cookie, header):
                return JSONResponse({"detail": "CSRF check failed"}, status_code=403)

        response = await call_next(request)

        if self.cookie_name not in request.cookies:
            response.set_cookie(
                self.cookie_name,
                secrets.token_urlsafe(32),
                httponly=False,  # the frontend must read it
                secure=self.secure,
                samesite="lax",
                path="/",
            )
        return response
