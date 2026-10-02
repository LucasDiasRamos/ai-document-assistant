from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Question must not be empty")
        return normalized


class ChatSource(BaseModel):
    document_id: int
    document: str
    page: int


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
