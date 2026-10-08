from typing import Annotated
import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_embedding_provider_dependency
from app.api.errors import APIErrorCode, APIException
from app.core.database import get_db
from app.core.observability import log_event
from app.schemas.document import (
    APIError,
    DocumentDetail,
    DocumentListResponse,
    DocumentSummary,
    DocumentUploadResponse,
)
from app.services.document_service import (
    DEFAULT_DOCUMENT_LIST_LIMIT,
    MAX_DOCUMENT_LIST_LIMIT,
    DocumentFileCleanupError,
    DocumentTooLargeError,
    DocumentUploadValidationError,
    InvalidPdfSignatureError,
    UnsupportedDocumentTypeError,
    create_uploaded_document,
    delete_document,
    get_document_by_id,
    list_documents,
)
from app.services.embedding_service import (
    EmbeddingError,
    EmbeddingProvider,
)
from app.services.ingestion_service import (
    DocumentFailureStateError,
    DocumentIngestionError,
    process_document,
)
from app.services.pdf_service import PdfExtractionError
from app.services.storage_service import StorageService, get_storage_service

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": APIError},
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"model": APIError},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": APIError},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": APIError},
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
    log_event(
        logger,
        logging.INFO,
        "document.upload.started",
        operation="upload",
    )

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
        raise APIException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            code=APIErrorCode.UPLOAD_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except (
        UnsupportedDocumentTypeError,
        InvalidPdfSignatureError,
    ) as exc:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=APIErrorCode.UNSUPPORTED_FILE,
            detail=str(exc),
        ) from exc
    except DocumentUploadValidationError as exc:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=APIErrorCode.VALIDATION_ERROR,
            detail=str(exc),
        ) from exc
    except DocumentFailureStateError as exc:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=APIErrorCode.PROCESSING_FAILED,
            detail="Document processing state could not be persisted",
        ) from exc
    except (PdfExtractionError, DocumentIngestionError) as exc:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=APIErrorCode.PROCESSING_FAILED,
            detail=(
                document.error_message
                if document is not None
                else "Document processing failed"
            ),
        ) from exc
    except EmbeddingError as exc:
        raise APIException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=APIErrorCode.PROVIDER_UNAVAILABLE,
            detail=(
                document.error_message
                if document is not None
                else "Embedding provider unavailable"
            ),
        ) from exc
    finally:
        log_event(
            logger,
            logging.INFO,
            "document.upload.finished",
            operation="upload",
            document_id=(
                document.id
                if document is not None
                else None
            ),
            status=(
                document.status.value
                if document is not None
                else "rejected"
            ),
        )

    return DocumentUploadResponse.model_validate(document)



@router.get(
    "",
    response_model=DocumentListResponse,
)
def read_documents(
    db: Session = Depends(get_db),
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_DOCUMENT_LIST_LIMIT),
    ] = DEFAULT_DOCUMENT_LIST_LIMIT,
) -> DocumentListResponse:
    documents, total = list_documents(db, limit=limit)

    return DocumentListResponse(
        documents=[
            DocumentSummary.model_validate(document)
            for document in documents
        ],
        total=total,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": APIError},
    },
)
def read_document(
    document_id: int,
    db: Session = Depends(get_db),
) -> DocumentDetail:
    document = get_document_by_id(db, document_id)

    if document is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=APIErrorCode.DOCUMENT_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentDetail.model_validate(document)



@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": APIError},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": APIError},
    },
)
def remove_document(
    document_id: int,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> Response:
    document = get_document_by_id(db, document_id)

    if document is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=APIErrorCode.DOCUMENT_NOT_FOUND,
            detail="Document not found",
        )

    try:
        delete_document(
            db,
            document,
            storage=storage,
        )
    except DocumentFileCleanupError as exc:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=APIErrorCode.INTERNAL_ERROR,
            detail="Document deleted, but stored file cleanup failed",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
