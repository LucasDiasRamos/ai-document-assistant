# Backlog — AI Document Assistant

This backlog breaks the portfolio MVP into implementation tasks separated by **API** and **Web**.

Each task includes:
- **What** must be built;
- **How** it should be implemented;
- **Expected result**;
- **Tests** required before considering the task complete.

The intended product flow is:

```text
Upload PDF
   -> extract pages
   -> chunk text
   -> generate embeddings
   -> store in PostgreSQL + pgvector
   -> ask question
   -> retrieve relevant chunks
   -> send grounded context to LLM
   -> return answer + document/page citations
```

## Delivery order

Recommended order:

```text
API-01..API-14
    ->
WEB-01..WEB-07
    ->
API-15..API-18
    ->
WEB-08..WEB-11
    ->
hardening, tests and deployment
```

The frontend can begin after the document API contract is stable. The final chat UI should only be completed after the RAG endpoint shape is defined.

---

# API backlog

## API-00 — Project bootstrap

**Status:** Done

### What

Establish the initial backend structure and local database environment.

### How

- FastAPI application.
- Environment configuration with `pydantic-settings`.
- SQLAlchemy engine/session.
- PostgreSQL 16 using `pgvector/pgvector:pg16`.
- Backend Dockerfile.
- Health endpoints.
- Initial documentation.

### Expected result

The API starts locally and both application and database health can be verified.

### Tests

- `GET /health` returns HTTP 200.
- `GET /health/database` returns HTTP 200 when PostgreSQL is available.
- OpenAPI loads successfully.

---

## API-01 — Configuration hardening

**Status:** Done

### What

Make application configuration authoritative and reusable throughout the API.

### How

- Use `settings.app_name` when creating the FastAPI application.
- Keep configuration centralized in `app/core/config.py`.
- Add future settings for upload limits, storage path, chunking, retrieval, embedding provider, and LLM provider only when those features are introduced.
- Never read environment variables directly from feature modules when a setting belongs in `Settings`.

### Expected result

Changing a supported environment variable changes application behavior without editing source code.

### Tests

- Override `APP_NAME` and verify the FastAPI/OpenAPI title changes.
- Verify missing required settings fail clearly.
- Verify default values are applied where documented.

---

## API-02 — Alembic setup and pgvector migration

**Status:** Done

**Depends on:** API-00

### What

Introduce database migrations and enable the vector extension through versioned database setup.

### How

- Run `alembic init` under `backend/`.
- Point Alembic at the SQLAlchemy metadata.
- Read `DATABASE_URL` from application settings.
- Create an initial migration that executes:
  `CREATE EXTENSION IF NOT EXISTS vector`.
- Do not rely on manual extension creation as the final developer workflow.

### Expected result

A fresh PostgreSQL database can be brought to the expected schema state with one Alembic upgrade command.

### Tests

- Create a clean database.
- Run `alembic upgrade head`.
- Verify the `vector` extension exists.
- Run downgrade/upgrade where safe.
- Verify migration is idempotent when applied in a clean environment.

---

## API-03 — Document model

**Status:** Done

**Depends on:** API-02

### What

Persist metadata and processing state for every uploaded document.

### How

Create a SQLAlchemy `Document` model with at least:

- `id`
- `filename`
- `original_filename`
- `file_path`
- `status`
- `error_message` nullable
- `created_at`
- `updated_at`

Use an enum or constrained values for:

- `uploaded`
- `processing`
- `processed`
- `failed`

Add an Alembic migration.

### Expected result

The backend can create, read, update processing status, and delete document metadata.

### Tests

- Insert a document.
- Read it by ID.
- Update status.
- Persist a failure message.
- Delete it.
- Verify invalid status values are rejected.

---

## API-04 — DocumentChunk model with pgvector

**Status:** Done

**Depends on:** API-02, API-03

### What

Persist searchable chunks and their vector embeddings.

### How

Create `DocumentChunk` with at least:

- `id`
- `document_id`
- `content`
- `page_number`
- `chunk_index`
- `embedding`
- `created_at`

Requirements:

- foreign key to `Document`;
- cascade deletion;
- pgvector `Vector` column;
- embedding dimension treated as schema-owned and changed only through a migration plus matching ORM update;
- index strategy added when retrieval implementation is ready.

### Expected result

A document can own multiple chunks with content, page traceability, and embeddings.

### Tests

- Insert a document and multiple chunks.
- Read chunks in chunk order.
- Verify page metadata persists.
- Delete the parent document and confirm child chunks are removed.
- Verify an embedding of the configured dimension can be stored.

---

## API-05 — Document schemas

**Status:** Done

**Depends on:** API-03

### What

Define stable request/response schemas for document endpoints.

### How

Create Pydantic models for:

- document summary;
- document detail;
- upload response;
- processing status;
- document list response;
- structured API error when appropriate.

Do not expose internal storage paths in public responses.

### Expected result

The document API has documented and predictable OpenAPI contracts.

### Tests

- Serialize a valid document.
- Confirm private/internal fields are omitted.
- Validate status values.
- Validate expected JSON shapes through endpoint tests.

---

## API-06 — Safe local file storage service

**Status:** Done

**Depends on:** API-01

### What

Store uploaded PDFs safely during the MVP.

### How

Create a storage service that:

- receives uploaded file bytes/stream;
- generates an internal UUID-based filename;
- preserves original filename only as metadata;
- creates storage directories when necessary;
- prevents path traversal;
- supports deletion;
- uses a configurable storage root.

Never use a client-supplied filename directly as a filesystem path.

### Expected result

Uploaded documents are stored safely without filename collisions or arbitrary path access.

### Tests

- Save a valid PDF.
- Save two files with the same original name and confirm unique internal filenames.
- Test suspicious names such as `../../file.pdf`.
- Delete a stored file.
- Verify missing-file deletion is handled predictably.

---

## API-07 — PDF upload endpoint

**Status:** Done

**Depends on:** API-03, API-05, API-06

### What

Expose `POST /api/documents`.

### How

- Accept multipart PDF uploads.
- Validate MIME type and extension.
- Add configurable maximum upload size.
- Store the file through the storage service.
- Create the `Document` record.
- Return document ID and initial status.
- Keep route code thin; orchestration belongs in a service.

The first version may process synchronously. Background processing can be introduced only if processing time makes it necessary.

### Expected result

A user can upload a valid PDF and receive a persisted document record.

### Tests

- Upload valid PDF -> success.
- Upload non-PDF -> 4xx.
- Empty file -> 4xx.
- File over size limit -> 4xx.
- Duplicate original filename -> allowed with unique internal storage.
- Database failure does not silently leave inconsistent state.

---

## API-08 — PDF text extraction

**Status:** Done

**Depends on:** API-07

### What

Extract text from PDFs while preserving source page numbers.

### How

Create `pdf_service.py` using PyMuPDF.

Return a structure similar to:

```python
[
    {"page": 1, "text": "..."},
    {"page": 2, "text": "..."},
]
```

Requirements:

- preserve 1-based page numbers for user-facing citations;
- normalize obviously broken whitespace conservatively;
- do not join all pages before metadata is captured;
- raise an explicit processing error for unreadable/corrupt PDFs.

OCR is outside the initial scope.

### Expected result

Text-based PDFs produce page-aware text ready for chunking.

### Tests

- Single-page PDF.
- Multi-page PDF.
- Verify text from each page maps to the correct page number.
- Corrupt PDF -> controlled failure.
- Blank page -> handled without crashing.

---

## API-09 — Chunking service

**Status:** Done

**Depends on:** API-08

### What

Split extracted text into retrieval-sized overlapping chunks.

### How

Create `chunk_service.py`.

Initial parameters:

- approximately 800 tokens per chunk;
- 100–150 token overlap;
- configurable values;
- preserve source page metadata;
- assign deterministic `chunk_index` values.

Start with a simple implementation that can be understood and tested. Do not introduce a RAG framework just for chunking.

### Expected result

Large page-aware text becomes an ordered list of chunks that retain document/page traceability.

### Tests

- Short text produces one chunk.
- Long text produces multiple chunks.
- Neighboring chunks contain the configured overlap.
- Chunk indexes are ordered.
- Source page metadata survives chunking.
- Empty text is handled safely.

---

## API-10 — Embedding provider abstraction

**Status:** Done

**Depends on:** API-01

### What

Create a replaceable embedding service instead of coupling business logic directly to one SDK.

### How

Define a simple interface/protocol such as:

- `embed_text(text)`
- `embed_batch(texts)`

Add the first concrete provider.

Configuration should define:

- provider;
- model;
- embedding model compatibility with the schema-owned vector dimension;
- API key.

Validate that provider dimension matches the pgvector schema.

### Expected result

The ingestion and query pipelines can request embeddings without knowing provider-specific SDK details.

### Tests

- Mock provider returns predictable embeddings.
- Batch input preserves order.
- Provider errors become controlled application errors.
- A provider/model whose embedding size does not match the current database schema is rejected.
- Tests do not call paid APIs by default.

---

## API-11 — Document ingestion orchestrator

**Status:** Done

**Depends on:** API-04, API-08, API-09, API-10

### What

Connect PDF extraction, chunking, embeddings, and persistence into one ingestion workflow.

### How

Create a document processing service:

1. set document status to `processing`;
2. extract pages;
3. create chunks;
4. generate embeddings;
5. persist chunks;
6. set status to `processed`.

On failure:

- rollback incomplete DB work where appropriate;
- set document to `failed`;
- store a safe error message;
- log technical details.

### Expected result

One uploaded PDF becomes a searchable collection of vectorized chunks.

### Tests

- Happy-path ingestion.
- Extraction failure -> failed status.
- Embedding failure -> failed status.
- Correct number of chunks persisted.
- Every chunk contains page number and embedding.
- No partially successful state is reported as processed.

---

## API-12 — List and inspect documents

**Status:** Done

**Depends on:** API-03, API-05

### What

Expose document retrieval endpoints.

### How

Implement:

- `GET /api/documents`
- `GET /api/documents/{document_id}` if useful for the Web client.

Return processing status and user-safe metadata.

Add pagination before it becomes necessary; a simple bounded list is acceptable for the first MVP.

### Expected result

The frontend can load uploaded documents and determine whether each is ready, processing, or failed.

### Tests

- Empty list.
- List multiple documents.
- Fetch known document.
- Unknown ID -> 404.
- Internal file paths are never returned.

---

## API-13 — Delete document and derived data

**Status:** Done

**Depends on:** API-04, API-06, API-12

### What

Expose `DELETE /api/documents/{document_id}`.

### How

Deletion must remove:

- database document record;
- all chunks/vectors;
- stored source file.

Use database cascades for chunk records and storage service deletion for files.

Define behavior for partially missing files so database cleanup can still succeed safely.

### Expected result

Deleting a document removes it from the application and from future retrieval.

### Tests

- Delete existing document.
- Verify chunks are gone.
- Verify file is gone.
- Unknown ID -> 404.
- Missing local file does not leave database record undeletable.

---

## API-14 — Vector similarity retrieval

**Status:** Done

**Depends on:** API-04, API-10, API-11

### What

Retrieve the most semantically relevant chunks for a user question.

### How

Create `retrieval_service.py`:

1. embed the question;
2. query pgvector similarity;
3. return configurable top-k results;
4. return content plus document/page metadata;
5. optionally filter only documents with `processed` status.

Start with pure semantic retrieval. Do not add reranking or hybrid search before measuring the baseline.

### Expected result

A question about known document content returns the expected supporting chunks near the top of the result set.

### Tests

- Seed deterministic test vectors.
- Query near one known vector.
- Verify ranking order.
- Verify `top_k` limit.
- Verify citation metadata is returned.
- Verify chunks from failed/unprocessed documents are excluded if that rule is implemented.

---

## API-15 — LLM provider abstraction

**Status:** Done

**Depends on:** API-01

### What

Create a provider-neutral generation service.

### How

Define an interface such as:

- `generate(messages)`
- optional future `stream(messages)`

Configuration should define provider/model and secrets.

Keep retry/timeouts and provider error translation inside this layer.

### Expected result

RAG logic can generate answers without being coupled directly to an LLM vendor SDK.

### Tests

- Mock successful generation.
- Timeout/error mapping.
- Missing credential configuration.
- Tests never require a paid provider.

---

## API-16 — RAG prompt and context builder

**Status:** Done

**Depends on:** API-14, API-15

### What

Build the grounded prompt from retrieved chunks.

### How

Create a small explicit prompt builder that:

- tells the model to answer only from supplied context;
- instructs it to say when information is not present;
- labels each context block with document/page;
- avoids asking the model to invent citations;
- keeps citation data separately available to API code.

Example context block:

```text
[Source: manual.pdf | Page: 17]
...
```

### Expected result

Generation receives clear, traceable document context and a strict grounding instruction.

### Tests

- Prompt includes question.
- Prompt includes retrieved content.
- Prompt includes source metadata.
- Prompt includes insufficient-context instruction.
- Empty retrieval result produces the expected safe flow.

---

## API-17 — Chat/RAG endpoint

**Status:** Done

**Depends on:** API-14, API-15, API-16

### What

Expose `POST /api/chat`.

### How

Request:

```json
{
  "question": "What is the warranty period?"
}
```

Flow:

1. validate question;
2. retrieve top-k chunks;
3. build grounded context;
4. call LLM;
5. return answer;
6. return deduplicated source references.

Response:

```json
{
  "answer": "...",
  "sources": [
    {
      "document_id": 1,
      "document": "manual.pdf",
      "page": 17
    }
  ]
}
```

### Expected result

A user can ask a question and receive a grounded answer with traceable citations.

### Tests

- Supported question returns answer and sources.
- Empty question -> 4xx.
- Sources correspond to retrieved chunks.
- Duplicate source/page pairs are deduplicated.
- LLM failure -> controlled 5xx/503 response.

---

## API-18 — Insufficient-context behavior

**Status:** Done

**Depends on:** API-14, API-17

### What

Prevent confident answers when retrieval does not support the question.

### How

- Establish a retrieval confidence/quality rule.
- If no acceptable context exists, skip or tightly constrain generation.
- Return a stable response indicating that the answer was not found in uploaded documents.
- Do not attach unrelated citations.

Keep the first rule simple and measurable.

### Expected result

Questions outside the uploaded knowledge base do not receive fabricated document answers.

### Tests

- Ask an unrelated question.
- Verify response indicates insufficient information.
- Verify no irrelevant citations are returned.
- Verify a supported question still works.

---

## API-19 — Conversation history

**Status:** Later / Should-have

**Depends on:** API-17

### What

Persist or maintain chat history for a better conversation experience.

### How

If implemented in the portfolio MVP:

- create `Conversation` and `Message` models;
- associate messages with one conversation;
- distinguish user/assistant roles;
- preserve source metadata for assistant messages;
- decide explicitly how much history is sent back to the model.

Do not let unlimited history inflate token cost.

### Expected result

Users can return to a conversation and see previous questions and answers.

### Tests

- Create conversation.
- Add messages in order.
- Reload conversation.
- Verify citations persist with assistant messages.
- Verify history window/token limits.

---

## API-20 — Unified API errors and validation

**Status:** Done

**Depends on:** document and chat endpoints

### What

Make failures predictable for the frontend.

### How

Define consistent errors for:

- validation;
- unsupported file;
- missing document;
- processing failure;
- provider unavailable;
- database unavailable.

Avoid leaking stack traces, API keys, local paths, or provider internals.

### Expected result

The frontend can map API failures to useful user messages.

### Tests

- Trigger each relevant error category.
- Assert HTTP status.
- Assert response schema.
- Assert sensitive implementation details are absent.

---

## API-21 — Logging and observability

**Status:** Done

### What

Add useful structured application logging.

### How

Log at minimum:

- document upload start/end;
- processing success/failure;
- number of chunks;
- retrieval duration/result count;
- provider request duration;
- application errors.

Do not log full documents, secrets, embeddings, or unnecessary user content.

### Expected result

A failed ingestion or chat request can be diagnosed from logs without exposing sensitive content.

### Tests

- Verify expected log events through captured logs.
- Verify secrets are not logged.
- Verify failure paths include document/request context.

---

## API-22 — Automated RAG evaluation fixtures

**Status:** Done

**Depends on:** API-17, API-18

### What

Create a small repeatable quality suite for retrieval and grounded answers.

### How

Add sample public/synthetic PDFs plus a fixture containing:

- known questions;
- expected source page(s);
- questions intentionally not answerable.

Measure retrieval correctness separately from LLM wording.

### Expected result

Changes to chunking, embeddings, or retrieval can be compared against a baseline instead of judged only manually.

### Tests

- Expected page is present in top-k for known questions.
- Unsupported questions fail the support threshold.
- Evaluation can run without paid generation when only retrieval is being tested.

---

## API-23 — Run backend in Docker Compose

**Status:** Done

**Depends on:** stable API startup

### What

Add the backend service to Docker Compose.

### How

- Build from `backend/Dockerfile`.
- Connect to PostgreSQL using the Compose service hostname.
- Add dependency/health behavior.
- Mount development storage only when appropriate.
- Keep production concerns separate from dev convenience.

### Expected result

A developer can run the backend and database together with Docker Compose.

### Tests

- Clean `docker compose up --build`.
- API health becomes healthy.
- Database endpoint succeeds.
- Container restart does not destroy PostgreSQL volume data.

---

## API-24 — CI for backend

**Status:** Done

### What

Run backend validation automatically on pull requests.

### How

Add GitHub Actions for:

- dependency installation;
- tests;
- optional lint/format checks;
- a PostgreSQL/pgvector service where integration tests require it.

Do not require external paid AI services.

### Expected result

Breaking backend changes are detected before merge.

### Tests

- Open a PR with passing code -> green workflow.
- Confirm a deliberately failing test makes CI fail.

---

## API-25 — API security hardening for public demo

**Status:** Done (security baseline; tenant isolation remains outside MVP)

### What

Protect the public demo from obvious abuse.

### How

At minimum:

- strict upload size;
- PDF validation;
- safe filenames;
- CORS restricted to the deployed frontend;
- provider timeouts;
- basic rate limiting if publicly exposed;
- secret management through hosting platform;
- no debug traces in production.

Authentication remains outside the initial public portfolio MVP unless abuse risk requires it.

### Expected result

The demo is reasonably safe to expose publicly without trivial file/path or unlimited-request abuse.

### Tests

- Oversized upload.
- Invalid content type.
- Path traversal filename.
- Disallowed CORS origin.
- Provider timeout.
- Rate-limit behavior if implemented.

---

## API-26 — Backend deployment

**Status:** Todo

**Depends on:** API-23, API-24, API-25

### What

Deploy the API and PostgreSQL to a stable public environment.

### How

Choose a platform that supports:

- Python/Docker;
- PostgreSQL with pgvector;
- environment secrets;
- persistent storage/object storage strategy.

For public deployment, move source PDFs away from ephemeral local filesystem if the platform does not guarantee persistence.

### Expected result

A public HTTPS API supports the portfolio demo.

### Tests

- Production health.
- Database connectivity.
- Upload a sample PDF.
- Complete ingestion.
- Ask a known question.
- Confirm citation.
- Restart/redeploy and verify expected persistence.

---

# Web backlog

## WEB-01 — Frontend bootstrap

**Status:** Done

### What

Create the frontend application.

### How

Use React + Vite + TypeScript.

Set up:

- `src/components`;
- `src/features/documents`;
- `src/features/chat`;
- `src/services`;
- `src/types`;
- `src/styles`.

Add environment configuration for API base URL.

### Expected result

The frontend starts locally and renders a minimal application shell.

### Tests

- Build succeeds.
- Development server starts.
- Basic app smoke test renders.
- Missing/invalid required frontend environment values are handled clearly.

---

## WEB-02 — Application shell and responsive layout

**Status:** Done

**Depends on:** WEB-01

### What

Build the main visual structure.

### How

Desktop layout:

```text
+----------------+--------------------------------+
| Documents      | Chat                           |
|                |                                |
| files          | messages                       |
|                |                                |
| + Upload       | question input                 |
+----------------+--------------------------------+
```

On narrow screens, switch to a stacked or drawer-based document view.

### Expected result

The app already looks like a coherent product before feature wiring begins.

### Tests

- Desktop viewport.
- Tablet/mobile viewport.
- No horizontal overflow.
- Keyboard navigation reaches primary controls.

---

## WEB-03 — API client layer and shared types

**Status:** Done

**Depends on:** WEB-01, stable API contracts

### What

Centralize HTTP communication.

### How

Create a small API client for:

- list documents;
- upload document;
- delete document;
- send chat question.

Use TypeScript types matching API response schemas.

Centralize:

- base URL;
- JSON parsing;
- error parsing;
- request timeout/cancellation where useful.

### Expected result

Components do not scatter raw `fetch` calls and URL strings across the app.

### Tests

- Mock successful request.
- Mock API error.
- Verify response mapping.
- Verify network failure becomes a predictable client error.

---

## WEB-04 — Document list/sidebar

**Status:** Done

**Depends on:** WEB-02, WEB-03, API-12

### What

Display uploaded documents and processing state.

### How

For each document show:

- original filename;
- status;
- optional uploaded timestamp;
- failed state when applicable.

Add empty-state UI when no documents exist.

### Expected result

Users can immediately see which documents are available for Q&A.

### Tests

- Empty list.
- One document.
- Multiple documents.
- Processing/processed/failed states.
- API failure state.

---

## WEB-05 — Upload interaction

**Status:** Done

**Depends on:** WEB-03, API-07

### What

Allow PDF selection and upload.

### How

Support:

- file picker;
- optional drag-and-drop;
- PDF-only UX validation;
- upload progress/loading state;
- success refresh;
- API validation errors.

Do not treat client validation as a replacement for backend validation.

### Expected result

A user can upload a PDF from the browser and see it appear in the document list.

### Tests

- Select valid PDF.
- Reject obvious non-PDF selection in UI.
- Successful upload.
- Server rejection.
- Network failure.
- Upload button disabled while the same request is active.

---

## WEB-06 — Processing status refresh

**Status:** Done

**Depends on:** WEB-04, WEB-05, API-11/API-12

### What

Keep document state updated while ingestion is running.

### How

For synchronous ingestion, refresh after upload completion.

If processing becomes asynchronous:

- poll only documents in transitional states;
- stop polling when processed/failed;
- avoid unbounded polling.

### Expected result

The user sees when a document becomes ready for questions without manually refreshing the page.

### Tests

- Uploaded -> processing -> processed.
- Processing -> failed.
- Polling stops at terminal state.
- Component cleanup stops active polling.

---

## WEB-07 — Delete document interaction

**Status:** Done

**Depends on:** WEB-04, API-13

### What

Allow deletion of an uploaded document.

### How

- add delete action;
- show confirmation;
- disable repeated deletion while pending;
- remove item after success;
- restore/retain UI state on failure.

### Expected result

Users can remove documents cleanly from the interface.

### Tests

- Cancel confirmation.
- Confirm successful delete.
- Delete failure.
- Document disappears only after successful behavior.

---

## WEB-08 — Chat message interface

**Status:** Done

**Depends on:** WEB-02

### What

Build the chat presentation independently of live AI.

### How

Create reusable components for:

- user message;
- assistant message;
- citation list;
- composer/input;
- empty chat state.

Use fixture messages first.

### Expected result

The application can visually represent a complete question/answer exchange before API integration.

### Tests

- User message rendering.
- Assistant message rendering.
- Long answer wrapping.
- Multiple citations.
- Empty conversation state.

---

## WEB-09 — Chat API integration

**Status:** Done

**Depends on:** WEB-03, WEB-08, API-17

### What

Connect the question composer to the RAG endpoint.

### How

- submit non-empty question;
- immediately render the user's message;
- show pending assistant state;
- call `POST /api/chat`;
- render returned answer and sources;
- prevent accidental duplicate submissions;
- keep input usable after response.

### Expected result

A user can ask a question in the browser and receive a grounded answer.

### Tests

- Successful question.
- Empty question blocked.
- Loading state.
- API failure.
- Multiple sequential questions.
- Duplicate rapid submit prevention.

---

## WEB-10 — Citation/source UI

**Status:** Done

**Depends on:** WEB-09

### What

Make source traceability obvious.

### How

Render citations as compact source chips/cards containing:

- document filename;
- page number.

Later enhancements may include document preview/highlighting, but the MVP should not require them.

### Expected result

Every grounded answer clearly tells the user where supporting information came from.

### Tests

- One citation.
- Multiple citations.
- Duplicate citation handling.
- Long filename behavior.
- Answer without citations in insufficient-context flow.

---

## WEB-11 — Insufficient-context and error UX

**Status:** Done

**Depends on:** WEB-09, API-18/API-20

### What

Clearly distinguish “not found in documents” from technical failure.

### How

Create separate UX for:

- answer not supported by documents;
- network/API error;
- provider temporarily unavailable;
- no processed documents yet.

Do not show a generic red error for legitimate “not found” responses.

### Expected result

Users understand whether the system lacks source information or whether the application itself failed.

### Tests

- Unsupported question.
- API 5xx.
- Network offline.
- No searchable documents.
- Retry path where appropriate.

---

## WEB-12 — Conversation history

**Status:** Later / Should-have

**Depends on:** API-19, WEB-09

### What

Let users retain or reopen a conversation.

### How

If backend persistence exists:

- load messages by conversation;
- preserve ordering;
- preserve citations;
- add new-conversation action.

If history is postponed, keep only local in-session messages.

### Expected result

The chat experience can preserve useful context without changing the core document workflow.

### Tests

- Load existing conversation.
- Add new messages.
- New conversation clears active view.
- Citation metadata remains intact.

---

## WEB-13 — Accessibility and keyboard behavior

**Status:** Done

### What

Make the application usable without relying only on mouse interactions.

### How

- semantic buttons/forms;
- labels for upload and chat fields;
- visible focus state;
- sensible tab order;
- status messages via appropriate ARIA live regions;
- sufficient contrast;
- keyboard submission without trapping focus.

### Expected result

Core upload, document management, and chat flows are keyboard accessible and screen-reader friendly.

### Tests

- Navigate core UI by keyboard.
- Run accessibility checks.
- Verify form labels.
- Verify async status announcements where applicable.

---

## WEB-14 — Frontend automated tests

**Status:** Done

**Depends on:** stable Web features

### What

Protect critical user journeys.

### How

Use a test stack appropriate to Vite/React, such as Vitest + React Testing Library.

Prioritize behavior over implementation details.

Cover:

- document list;
- upload;
- delete;
- chat;
- citations;
- error states.

### Expected result

UI regressions in the main portfolio flow are caught automatically.

### Tests

This task itself is complete when the above feature tests run reliably in one command.

---

## WEB-15 — End-to-end happy-path test

**Status:** Todo

**Depends on:** completed API + Web core flows

### What

Verify the complete product from browser to database/LLM boundary.

### How

Use Playwright or an equivalent E2E tool.

Scenario:

1. open app;
2. upload a known sample PDF;
3. wait until processed;
4. ask a known question;
5. verify answer is displayed;
6. verify expected filename/page citation appears;
7. delete document.

Use a deterministic/mock generation provider in CI if needed.

### Expected result

The primary user story is verified as one integrated workflow.

### Tests

The scenario above must pass locally and in CI.

---

## WEB-16 — Portfolio polish

**Status:** Todo

**Depends on:** core functionality

### What

Turn the working MVP into a strong case study rather than a raw engineering demo.

### How

Add:

- clear product name/tagline;
- polished empty state;
- concise onboarding text;
- intentional loading skeleton/spinner;
- professional spacing/typography;
- sample question suggestions;
- clean error messages;
- project screenshots.

Avoid decorative complexity that slows the app or distracts from the product.

### Expected result

A potential freelance client can understand the problem and product within seconds.

### Tests

- Manual visual review at desktop and mobile sizes.
- No broken overflow with long filenames/answers.
- Core actions remain discoverable without instructions.

---

## WEB-17 — Web CI and production build

**Status:** Todo

**Depends on:** WEB-14

### What

Validate the frontend on every pull request.

### How

CI should run:

- dependency install;
- unit/component tests;
- production build;
- optional lint/format checks.

### Expected result

A PR cannot silently break the deployable frontend build.

### Tests

- Passing branch -> green CI.
- Deliberately broken test/build -> failed workflow.

---

## WEB-18 — Frontend deployment

**Status:** Todo

**Depends on:** WEB-17, API-26

### What

Deploy the browser application.

### How

- configure production API base URL;
- configure allowed API CORS origin;
- deploy to Vercel or equivalent static/frontend hosting;
- verify HTTPS;
- ensure refresh/navigation behavior works.

### Expected result

A public portfolio URL can be shared with prospective clients.

### Tests

- Open deployed site.
- List documents.
- Upload sample PDF.
- Ask question.
- View citation.
- Delete document.
- Test mobile viewport.

---

# Final portfolio completion checklist

The project is ready to be treated as a finished case when all of the following are true:

- [ ] A new developer can run it from the README.
- [ ] PostgreSQL + pgvector initialize through migrations.
- [ ] A PDF can be uploaded safely.
- [ ] Text is extracted with correct page metadata.
- [ ] Chunks and embeddings are persisted.
- [ ] Semantic retrieval returns relevant context.
- [ ] The LLM answer is grounded in retrieved context.
- [ ] Answers expose document/page citations.
- [ ] Unsupported questions do not fabricate document facts.
- [ ] The Web app supports upload, document status, chat, citations, and deletion.
- [ ] Critical API tests pass.
- [ ] Critical Web tests pass.
- [ ] An E2E happy path passes.
- [ ] CI runs on pull requests.
- [ ] Public demo is deployed.
- [ ] README includes screenshots and architecture.
- [ ] A short demo video is recorded for portfolio/Upwork.
