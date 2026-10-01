from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_embedding_provider_dependency
from app.core.database import get_db
from app.schemas.document import APIError, DocumentUploadResponse
from app.services.document_service import (
    DocumentTooLargeError,
    DocumentUploadValidationError,
    create_uploaded_document,
)
from app.services.embedding_service import (
    EmbeddingError,
    EmbeddingProvider,
)
from app.services.ingestion_service import (
    DocumentIngestionError,
    process_document,
)
from app.services.pdf_service import PdfExtractionError
from app.services.storage_service import StorageService, get_storage_service

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": APIError},
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"model": APIError},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": APIError},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": APIError},
    },
)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
    embedding_provider: EmbeddingProvider = Depends(
        get_embedding_provider_dependency
    ),
) -> DocumentUploadResponse:
    document = None

    try:
        document = create_uploaded_document(
            db,
            file,
            storage=storage,
        )
        process_document(
            db,
            document,
            embedding_provider,
        )
    except DocumentTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except DocumentUploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (PdfExtractionError, DocumentIngestionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                document.error_message
                if document is not None
                else "Document processing failed"
            ),
        ) from exc
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                document.error_message
                if document is not None
                else "Embedding provider unavailable"
            ),
        ) from exc

    return DocumentUploadResponse.model_validate(document)
