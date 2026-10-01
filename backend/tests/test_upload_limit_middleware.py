import asyncio

import pytest

from app.core.config import settings
from app.middleware.upload_limit import UploadRequestSizeLimitMiddleware


def test_streaming_request_without_content_length_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "max_upload_size_bytes", 4)
    monkeypatch.setattr(
        UploadRequestSizeLimitMiddleware,
        "MULTIPART_OVERHEAD_BYTES",
        0,
    )

    received_messages = iter(
        [
            {
                "type": "http.request",
                "body": b"1234",
                "more_body": True,
            },
            {
                "type": "http.request",
                "body": b"5",
                "more_body": False,
            },
        ]
    )
    sent_messages = []

    async def inner_app(scope, receive, send) -> None:
        while True:
            message = await receive()
            if not message.get("more_body", False):
                break

        await send(
            {
                "type": "http.response.start",
                "status": 204,
                "headers": [],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"",
            }
        )

    async def receive():
        return next(received_messages)

    async def send(message) -> None:
        sent_messages.append(message)

    middleware = UploadRequestSizeLimitMiddleware(inner_app)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/documents",
        "headers": [],
    }

    asyncio.run(middleware(scope, receive, send))

    response_start = next(
        message
        for message in sent_messages
        if message["type"] == "http.response.start"
    )
    assert response_start["status"] == 413
