from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Protect ToolGuard API routes with a shared API key.

    Health probes and the static dashboard remain reachable without credentials.
    Every route below ``/api/`` fails closed when no server-side key is configured.
    """

    def __init__(self, app, *, api_key: str | None) -> None:
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        if not self.api_key:
            return JSONResponse(
                status_code=503,
                content={"detail": "ToolGuard API authentication is not configured"},
            )

        supplied = request.headers.get("X-API-Key")
        if not supplied or not secrets.compare_digest(supplied, self.api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "invalid or missing API key"},
                headers={"WWW-Authenticate": "ApiKey"},
            )

        return await call_next(request)
