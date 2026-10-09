from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import APIErrorCode
from app.core.config import settings


class RequestBodyTooLargeError(Exception):
    pass


class UploadRequestSizeLimitMiddleware:
    """Bound upload request size before multipart parsing/spooling."""

    MULTIPART_OVERHEAD_BYTES = 64 * 1024

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if not self._is_document_upload(scope):
            await self.app(scope, receive, send)
            return

        request_limit = (
            settings.max_upload_size_bytes + self.MULTIPART_OVERHEAD_BYTES
        )

        content_length = self._content_length(scope)
        if content_length is not None and content_length > request_limit:
            await self._send_too_large(scope, receive, send)
            return

        received_bytes = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received_bytes

            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > request_limit:
                    raise RequestBodyTooLargeError

            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started

            if message["type"] == "http.response.start":
                response_started = True

            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except RequestBodyTooLargeError:
            if response_started:
                raise

            await self._send_too_large(scope, receive, send)

    @staticmethod
    def _is_document_upload(scope: Scope) -> bool:
        return (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path") == "/api/documents"
        )

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name.lower() != b"content-length":
                continue

            try:
                return int(value)
            except ValueError:
                return None

        return None

    @staticmethod
    async def _send_too_large(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "detail": "Upload request exceeds the allowed size",
                "code": str(APIErrorCode.UPLOAD_TOO_LARGE),
            },
        )
        await response(scope, receive, send)
