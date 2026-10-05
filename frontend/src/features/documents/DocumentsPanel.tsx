import { useEffect, useState } from "react";

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
  const [reloadKey, setReloadKey] = useState(0);

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

      <button className="button button-primary upload-button" type="button">
        <span aria-hidden="true">+</span>
        Upload PDF
      </button>

      <p className="panel-footnote">
        PDF files only. Upload wiring arrives in the document workflow.
      </p>
    </aside>
  );
}
