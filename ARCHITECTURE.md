# Architecture

## 1. Overview

AI Document Assistant is a Retrieval-Augmented Generation (RAG) application. Its purpose is to answer user questions from uploaded documents while preserving traceability to the original source and page.

The MVP prioritizes a small, understandable architecture over framework-heavy abstractions.

## 2. Architectural goals

- Keep the RAG pipeline explicit and inspectable.
- Preserve source metadata from ingestion through final answers.
- Use one primary database for relational data and vectors.
- Make components replaceable through service boundaries.
- Avoid unnecessary infrastructure in the MVP.
- Support local development with Docker Compose.
- Keep the backend independently usable through REST APIs.

## 3. High-level architecture

```text
Frontend (React + Vite + TypeScript)
        |
        v
      FastAPI
        |
   +----+----+
   |         |
Document   Chat
 flow      flow
   |         |
PDF       Question
extract   embedding
   |         |
chunking  vector retrieval
   |         |
embeddings |
   +----+----+
        |
PostgreSQL + pgvector
        |
       LLM
        |
 answer + sources
```

## 4. Main components

### Frontend
The browser client is a React + Vite + TypeScript application under `frontend/`. Feature boundaries remain explicit with `components`, `features/documents`, `features/chat`, `services`, `types`, and `styles`. `VITE_API_BASE_URL` accepts either a same-origin root-relative API path or an absolute HTTP(S) API root and is validated at startup so configuration failures are detected before API calls begin. Local development uses `/api`, which Vite proxies to `http://localhost:8000` to avoid browser CORS requirements.

The application shell uses a two-column documents/chat workspace on larger screens and switches to a stacked layout below 860px. The shell includes semantic document/chat landmarks, a keyboard skip link, visible focus states, bounded content widths, and overflow-safe grid sizing.

Frontend HTTP access is centralized in a typed API client rather than scattered across components. Shared TypeScript contracts mirror the current FastAPI document and chat response schemas. The client exposes list/upload/delete/chat methods, applies operation-appropriate request timeouts, supports caller cancellation, leaves multipart boundaries to the browser, handles 204 responses without JSON parsing, and converts HTTP/network/timeout/cancellation/invalid-response failures into a predictable `ApiClientError` shape. Standard FastAPI 422 validation arrays are normalized into readable messages while preserving field location, validation type, and message for the UI.

The document sidebar loads the bounded document list on mount through the API client, cancels stale list requests during unmount, and renders explicit loading, empty, failure/retry, and populated states. Each document exposes the original filename, processing status, uploaded date, and user-safe failure message when present.

PDF upload is initiated through an accessible file picker and the typed API client. The browser performs only an obvious PDF filename/MIME pre-check for user experience; backend validation remains authoritative. While an upload is active, the picker and upload button are disabled to prevent duplicate submission, the request is cancellable on unmount, API/network errors remain visible without discarding the existing document list, and a successful synchronous upload triggers a fresh document-list request.

The current backend ingestion path is synchronous, so the post-upload refresh normally observes a terminal status immediately. As a future-safe fallback, the document panel polls only while at least one document remains in `uploaded` or `processing`. Polls run sequentially every 2 seconds, stop immediately when all documents become `processed` or `failed`, abort on component cleanup, tolerate transient refresh failures, and are capped at 30 attempts so polling cannot continue indefinitely.

Document deletion uses an inline confirmation before calling the typed delete endpoint. The UI follows a pessimistic mutation model: the document remains visible while deletion is pending and is removed from local state only after the backend confirms success. Repeated delete actions are disabled during the active request, transitional-status polling pauses to avoid stale list races, delete errors are shown next to the retained document for retry, and an active delete request is aborted if the component unmounts.

The chat presentation layer is componentized independently from the RAG transport. `ChatPanel` composes reusable user/assistant message rendering, citation lists, an empty conversation state, and a controlled composer. Long message content uses overflow-safe wrapping and citations remain separate from answer text.

The live chat flow uses the typed API client directly. A valid question is appended to local conversation state immediately, the composer is cleared and disabled while one request is active, and a pending assistant state is rendered until `POST /api/chat` returns. Successful responses append the grounded answer and backend-provided source metadata. A synchronous request-controller guard prevents duplicate rapid submissions before React can re-render, while the visible disabled state prevents ordinary repeat clicks. Failures retain the user's question, surface a safe inline error, and restore the composer for the next question. `New chat` aborts any active request and clears local conversation state; stale responses are ignored by controller identity checks.

### FastAPI
Exposes REST endpoints, validates requests/responses, coordinates services, and exposes health checks.

Planned endpoints:
```text
GET  /health
GET  /health/database
POST /api/documents
GET  /api/documents
GET  /api/documents/{document_id}
DELETE /api/documents/{document_id}
POST /api/chat
```

### PostgreSQL
Stores documents, chunks, metadata, and later conversation history.

### pgvector
Adds vector data types and similarity operations to PostgreSQL, avoiding a second vector database in the MVP.

### Local file storage
The MVP stores source PDFs under the configured `STORAGE_ROOT`. Client filenames are never used as filesystem paths; files receive UUID-based internal names, and delete operations reject paths outside the configured root.

### PyMuPDF
Extracts text page by page using plain-text extraction with reading-order sorting. Page numbers are converted to 1-based values for user-facing citations, blank pages are preserved with empty text, and corrupt/non-PDF/password-protected files raise controlled extraction errors. OCR is intentionally outside the MVP.

### Embedding service
Converts text into vectors behind a replaceable provider boundary. The MVP defines a provider protocol with single-text and batch embedding methods and uses OpenAI as the first concrete implementation. The default model is `text-embedding-3-small`, with the requested output dimension fixed to the database schema's `1536`. Provider responses are validated before persistence so dimension mismatches cannot silently reach pgvector. Large embedding workloads are partitioned into bounded provider requests while preserving global result order.

### Ingestion orchestrator
Coordinates PDF extraction, page-aware chunking, batch embedding generation, chunk persistence, and document status transitions. The MVP invokes this synchronously after a successful upload. Processing state is persisted before external work begins; chunks and the final `processed` state are committed together. During reprocessing, existing chunk deletions are flushed before replacement inserts to avoid unique-index collisions. Failures roll back incomplete work, retain existing chunks during failed reprocessing, persist a user-safe `failed` message, and log only safe technical diagnostics such as document ID and exception types.

### Document read/delete API
Exposes a bounded document list and single-document detail using public schemas only. The list is ordered newest-first, supports a maximum limit of 100 records per request, and returns the total number of documents. Internal storage filename/path fields are never serialized.

Deleting a document removes the database record first; `DocumentChunk` rows and vectors are removed through the configured database cascade. The source PDF is then deleted through the storage service. An already-missing source file is treated as successful cleanup so a stale filesystem state cannot make the database record undeletable. A database failure rolls back before file cleanup begins, while a genuine post-commit filesystem failure is surfaced and logged as a controlled cleanup error.

### Retrieval service
Embeds the user question through the provider boundary and queries pgvector using cosine distance (`<=>`). Only chunks whose parent document is `processed` are eligible. Results are ordered by nearest distance and returned with document ID, public filename, page number, chunk index, content, distance, and derived cosine similarity. The default `RETRIEVAL_TOP_K` is 5 and requests are bounded to at most 20 results. Query embeddings are validated against the schema-owned 1536 dimensions before SQL execution.

### RAG prompt builder
Builds a provider-neutral grounded prompt from a user question and retrieved document context. Each context block is labeled with public document name and page number, while citation metadata is kept separately from generated text. Document content is explicitly treated as untrusted data rather than instructions, reducing prompt-injection risk from uploaded PDFs. Empty retrieval is represented explicitly so later orchestration can choose a safe insufficient-context path.

### LLM service
Generation is hidden behind a provider-neutral `GenerationProvider` interface. The first implementation uses the OpenAI Responses API. `LLM_MODEL` is required explicitly rather than hardcoded in application code, while provider and timeout remain environment-configurable. Input messages are validated before provider calls, timeout failures are distinguished from other provider failures, and empty provider responses are rejected. Prompt construction remains a separate RAG concern rather than being embedded in the provider layer.

### Chat/RAG orchestration
`POST /api/chat` composes the retrieval, prompt-building, and generation services. The route accepts a bounded non-empty question, retrieves top-k processed-document chunks, filters them by the configured minimum cosine similarity, builds the grounded prompt from only accepted chunks, invokes the generation provider, and returns the answer plus deduplicated document/page sources. Citation data comes from retrieved database metadata rather than model-generated text. After retrieval is materialized, the read transaction is rolled back before any external generation request so database connections are not held during LLM latency. If retrieval returns no chunks or every retrieved chunk falls below the quality threshold, generation is skipped entirely and the stable insufficient-context response is returned with no sources. Provider failures are mapped to user-safe `503` responses without exposing provider details.

## 5. Data model

### Document
```text
id
filename
original_filename
file_path
status
error_message
created_at
updated_at
```

Statuses: `uploaded`, `processing`, `processed`, `failed`.

### DocumentChunk
```text
id
document_id
content
page_number
chunk_index
embedding
created_at
```

Relationship: `Document 1 ---- N DocumentChunk`.

## 6. Ingestion flow

1. Client uploads PDF.
2. ASGI middleware bounds the incoming request body before multipart parsing/spooling. The service then validates the exact file size, filename length, extension, MIME type, PDF signature, and non-empty content.
3. File is stored locally for the MVP. If database persistence fails, the stored file is removed before the error is propagated.
4. Document record is created with `uploaded` status.
5. The ingestion orchestrator persists `processing`.
6. PyMuPDF extracts text page by page and preserves 1-based page metadata.
7. Text is split into overlapping chunks.
8. Embeddings are generated in batch and validated against the schema dimension.
9. Chunks/vectors and the final `processed` status are committed together.
10. Any extraction, chunking, embedding, or persistence failure rolls back incomplete work and records `failed` with a safe message.

Important metadata: document ID, original filename, page number, and chunk index.

## 7. Query flow

1. User asks a question.
2. Question is converted to an embedding.
3. pgvector searches for nearest chunks.
4. Top-k chunks are selected.
5. Context is assembled with document/page metadata.
6. LLM receives system rules, context, and question.
7. Response is generated.
8. API returns the generated answer plus deduplicated source references derived from retrieval metadata.

## 8. Chunking strategy

Initial strategy:
- `CHUNK_SIZE=800`;
- `CHUNK_OVERLAP=120`;
- chunks never cross page boundaries;
- page attribution is preserved directly on every chunk;
- `chunk_index` is global and deterministic within a document;
- blank pages do not produce chunks;
- the MVP uses provider-neutral lexical units (words/punctuation) as an approximation of tokenizer tokens, avoiding coupling to a specific embedding vendor before a model is selected;
- CJK text and abnormally long uninterrupted tokens fall back to character-level spans so `CHUNK_SIZE` remains an effective upper bound even when whitespace word boundaries are absent.

The window settings are centralized and validated so overlap must be smaller than chunk size.

## 9. Retrieval strategy

Initial retrieval uses pgvector cosine distance with top-5 chunks by default, bounded to 20, and no reranker. Only processed documents participate, and query embedding dimensionality is checked before SQL execution. The RAG layer currently accepts only chunks with cosine similarity >= `RETRIEVAL_MIN_SIMILARITY`, defaulting to 0.70. This is an explicit MVP heuristic, not a universal semantic-relevance constant; API-22 evaluation fixtures should calibrate it against known supported and unsupported questions. Hybrid search, reranking, query rewriting, and additional metadata filtering are future options only if evaluation justifies them.

## 10. Grounding rules

The grounding instructions must:
- answer only from supplied document context;
- treat retrieved document text as untrusted data, not instructions;
- state when information is absent;
- avoid unsupported claims and outside knowledge;
- never invent source metadata or citation markers;
- keep source metadata available separately to API code.

## 11. Configuration

Current variables:
```text
APP_NAME
DATABASE_URL
STORAGE_ROOT
MAX_UPLOAD_SIZE_BYTES
CHUNK_SIZE
CHUNK_OVERLAP
EMBEDDING_PROVIDER
EMBEDDING_MODEL
EMBEDDING_TIMEOUT_SECONDS
OPENAI_API_KEY
RETRIEVAL_TOP_K
RETRIEVAL_MIN_SIMILARITY
LLM_PROVIDER
LLM_MODEL
LLM_TIMEOUT_SECONDS
```

Future variables may include additional generation-provider API keys. The embedding vector dimension is intentionally schema-owned rather than runtime-configurable; changing it requires a database migration and a matching ORM update.

Secrets must never be committed.

## 12. Development infrastructure

Docker Compose provides PostgreSQL with pgvector support through `pgvector/pgvector:pg16`.

Database schema changes are versioned with Alembic. Running `alembic upgrade head` enables the pgvector extension and creates the current relational/vector schema.

## 13. Testing strategy

- unit tests for chunking and services;
- API tests;
- database integration tests;
- retrieval tests with known expected chunks;
- manual RAG quality evaluation.

## 14. Security considerations

MVP:
- validate file type and size;
- sanitize storage filenames;
- do not expose arbitrary filesystem paths;
- keep API keys in environment variables;
- parameterize database access.

Later SaaS versions require authentication, tenant isolation, authorization, rate limiting, scanning, encrypted object storage, audit logging, and privacy/LGPD controls.

## 15. Explicit non-goals for the MVP

No payments, multi-tenancy, enterprise RBAC, OCR, agentic workflows, multiple vector databases, fine-tuning, or autonomous browsing.

## 16. Evolution path

```text
M0 Bootstrap
 -> M1 Document persistence
 -> M2 PDF ingestion
 -> M3 Embeddings + pgvector
 -> M4 Retrieval
 -> M5 LLM answer generation
 -> M6 Frontend
 -> M7 Quality/testing/deployment
```
