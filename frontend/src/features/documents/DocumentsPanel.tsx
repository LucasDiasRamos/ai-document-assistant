import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
} from "react";

import {
  ApiClientError,
  getApiClient,
  type ApiClient,
} from "../../services/apiClient";
import type {
  DocumentStatus,
  DocumentSummary,
} from "../../types/api";

const DOCUMENT_LIST_LIMIT = 50;

const STATUS_LABELS: Record<DocumentStatus, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  processed: "Ready",
  failed: "Failed",
};

function formatUploadedAt(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Upload date unavailable";
  }

  return `Uploaded ${new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
  }).format(date)}`;
}

function documentLoadError(error: unknown): string {
  if (error instanceof ApiClientError) {
    return error.message;
  }

  return "Unable to load documents";
}

function documentUploadError(error: unknown): string {
  if (error instanceof ApiClientError) {
    return error.message;
  }

  return "Unable to upload document";
}

function isPdfSelection(file: File): boolean {
  const hasPdfExtension = file.name.toLowerCase().endsWith(".pdf");
  const hasAcceptedType =
    file.type === "" || file.type === "application/pdf";

  return hasPdfExtension && hasAcceptedType;
}

function DocumentIcon() {
  return (
    <svg viewBox="0 0 24 24" role="presentation">
      <path d="M7 3.75h6.6L18.25 8.4V20.25H7z" />
      <path d="M13.5 3.75V8.5h4.75M9.5 12h6M9.5 15h6" />
    </svg>
  );
}

export interface DocumentsPanelProps {
  client?: ApiClient;
}

export function DocumentsPanel({
  client = getApiClient(),
}: DocumentsPanelProps) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadControllerRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    setIsLoading(true);
    setErrorMessage(null);

    client
      .listDocuments(DOCUMENT_LIST_LIMIT, {
        signal: controller.signal,
      })
      .then((response) => {
        if (!active) {
          return;
        }

        setDocuments(response.documents);
        setTotal(response.total);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }

        if (
          error instanceof ApiClientError &&
          error.kind === "cancelled"
        ) {
          return;
        }

        setDocuments([]);
        setTotal(0);
        setErrorMessage(documentLoadError(error));
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [client, reloadKey]);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      uploadControllerRef.current?.abort();
    };
  }, []);

  const handleFileSelection = async (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];

    if (!file || isUploading) {
      return;
    }

    setUploadError(null);

    if (!isPdfSelection(file)) {
      setUploadError("Please select a PDF file.");
      event.target.value = "";
      return;
    }

    const controller = new AbortController();
    uploadControllerRef.current = controller;
    setIsUploading(true);

    try {
      await client.uploadDocument(file, {
        signal: controller.signal,
      });

      if (mountedRef.current) {
        setReloadKey((value) => value + 1);
      }
    } catch (error: unknown) {
      if (
        error instanceof ApiClientError &&
        error.kind === "cancelled"
      ) {
        return;
      }

      if (mountedRef.current) {
        setUploadError(documentUploadError(error));
      }
    } finally {
      if (uploadControllerRef.current === controller) {
        uploadControllerRef.current = null;
      }

      if (mountedRef.current) {
        setIsUploading(false);

        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    }
  };

  const countLabel =
    total === 1 ? "1 document uploaded" : `${total} documents uploaded`;

  return (
    <aside className="documents-panel" aria-labelledby="documents-title">
      <div className="panel-heading">
        <div>
          <p className="section-kicker">Knowledge base</p>
          <h2 id="documents-title">Documents</h2>
        </div>
        <span className="document-count" aria-label={countLabel}>
          {isLoading ? "…" : total}
        </span>
      </div>

      <div className="documents-content">
        {isLoading ? (
          <div
            className="documents-loading"
            role="status"
            aria-live="polite"
          >
            <span className="loading-spinner" aria-hidden="true" />
            <span>Loading documents…</span>
          </div>
        ) : errorMessage ? (
          <div className="documents-error" role="alert">
            <div className="empty-icon error-icon" aria-hidden="true">
              !
            </div>
            <div>
              <h3>Could not load documents</h3>
              <p>{errorMessage}</p>
            </div>
            <button
              className="button button-secondary retry-button"
              type="button"
              onClick={() => setReloadKey((value) => value + 1)}
            >
              Try again
            </button>
          </div>
        ) : documents.length === 0 ? (
          <div className="documents-empty">
            <div className="empty-icon" aria-hidden="true">
              <DocumentIcon />
            </div>
            <div>
              <h3>No documents yet</h3>
              <p>
                Add a PDF to create a searchable knowledge base for
                grounded answers.
              </p>
            </div>
          </div>
        ) : (
          <ul className="document-list" aria-label="Uploaded documents">
            {documents.map((document) => (
              <li className="document-item" key={document.id}>
                <div className="document-icon" aria-hidden="true">
                  <DocumentIcon />
                </div>

                <div className="document-details">
                  <p className="document-name" title={document.original_filename}>
                    {document.original_filename}
                  </p>

                  <div className="document-meta">
                    <span
                      className={`document-status status-${document.status}`}
                    >
                      {STATUS_LABELS[document.status]}
                    </span>
                    <span>{formatUploadedAt(document.created_at)}</span>
                  </div>

                  {document.status === "failed" &&
                  document.error_message ? (
                    <p className="document-error-message">
                      {document.error_message}
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="upload-controls">
        <label className="sr-only" htmlFor="document-upload">
          Choose PDF to upload
        </label>
        <input
          ref={fileInputRef}
          className="sr-only"
          id="document-upload"
          type="file"
          accept=".pdf,application/pdf"
          disabled={isUploading}
          onChange={handleFileSelection}
        />

        <button
          className="button button-primary upload-button"
          type="button"
          disabled={isUploading}
          aria-busy={isUploading}
          onClick={() => fileInputRef.current?.click()}
        >
          {isUploading ? (
            <>
              <span
                className="button-spinner"
                aria-hidden="true"
              />
              Uploading…
            </>
          ) : (
            <>
              <span aria-hidden="true">+</span>
              Upload PDF
            </>
          )}
        </button>

        {uploadError ? (
          <p className="upload-error" role="alert">
            {uploadError}
          </p>
        ) : null}
      </div>

      <p className="panel-footnote">
        PDF files only. Server validation still applies after selection.
      </p>
    </aside>
  );
}
