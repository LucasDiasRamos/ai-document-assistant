"""In-process rate limiter for anonymous demo uploads and AI questions.

Uses ASGI peer IP, not untrusted X-Forwarded-For. A deployed ingress must
enforce real-client limits across proxy connections and multiple replicas.
"""
from __future__ import annotations

from asyncio import Lock
from collections import deque
from math import ceil
from time import monotonic

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings


class DemoRateLimitMiddleware:
    MAX_ACTIVE_BUCKETS = 4096

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._lock = Lock()
        self._buckets: dict[tuple[str, str], deque[float]] = {}

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        route = scope.get("path")
        if route == "/api/chat":
            budget = settings.chat_requests_per_minute
        elif route == "/api/documents":
            budget = settings.upload_requests_per_minute
        else:
            await self.app(scope, receive, send)
            return

        peer = scope.get("client")
        client_host = str(peer[0]) if peer else "unknown"
        key = (client_host, route)
        now = monotonic()
        window = settings.rate_limit_window_seconds
        retry_after: int | None = None

        async with self._lock:
            if len(self._buckets) >= self.MAX_ACTIVE_BUCKETS:
                self._buckets = {
                    name: entries
                    for name, entries in self._buckets.items()
                    if entries and now - entries[-1] < window
                }
            if key not in self._buckets and len(self._buckets) >= self.MAX_ACTIVE_BUCKETS:
                retry_after = window
            else:
                entries = self._buckets.setdefault(key, deque())
                while entries and now - entries[0] >= window:
                    entries.popleft()
                if len(entries) >= budget:
                    retry_after = max(1, ceil(window - (now - entries[0])))
                else:
                    entries.append(now)

        if retry_after is not None:
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "code": "rate_limited",
                },
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
