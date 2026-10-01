from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    status: DocumentStatus
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentSummary):
    pass


class DocumentUploadResponse(DocumentSummary):
    pass


class DocumentProcessingStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: DocumentStatus
    error_message: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
    total: int


class APIError(BaseModel):
    detail: str
    code: str | None = None
