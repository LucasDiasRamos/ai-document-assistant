"""Public conversation records never include database token hashes."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.chat import ChatSource


class ConversationCreated(BaseModel):
    token: str
    expires_at: datetime


class ConversationMessageView(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    sources: list[ChatSource]


class ConversationHistory(BaseModel):
    expires_at: datetime
    messages: list[ConversationMessageView]
