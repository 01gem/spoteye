"""Local-server guard: refuse cross-site writes to /api/ (a web page POSTing to 127.0.0.1).

Plain ASGI (not BaseHTTPMiddleware) so SSE streams pass through untouched.
"""

from __future__ import annotations

from collections.abc import Collection

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})
BLOCKED_MSG: str = "Cross-site request blocked."


class OriginCheckMiddleware:
    """403 for /api/ writes whose Origin is neither this server nor an allowed dev origin.

    Requests without an Origin header (curl, tests, the CLI) pass, and so does /docs "Try it out".
    """

    def __init__(self, app: ASGIApp, allowed_origins: Collection[str]) -> None:
        self.app = app
        self.allowed = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self._blocked(scope):
            await JSONResponse({"detail": BLOCKED_MSG}, status_code=403)(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _blocked(self, scope: Scope) -> bool:
        if scope["method"] in SAFE_METHODS or not scope["path"].startswith("/api/"):
            return False
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        if origin is None:
            return False
        return origin != f"http://{headers.get('host', '')}" and origin not in self.allowed
