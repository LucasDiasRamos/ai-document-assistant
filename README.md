# AI Document Assistant

AI-powered document question-answering application built as a portfolio-grade RAG project.

Users will be able to upload documents, ask natural-language questions about their contents, and receive grounded answers with document and page citations.

## Current status

Project bootstrap completed.

Implemented:

- FastAPI application
- API health endpoint
- PostgreSQL connectivity health endpoint
- SQLAlchemy base configuration
- Environment-based configuration
- PostgreSQL 16 + pgvector through Docker Compose
- Alembic migration chain with pgvector initialization
- `Document` and `DocumentChunk` persistence models
- Public document schemas
- Persistence/schema tests
- Safe local PDF storage with UUID filenames and path containment
- PDF upload endpoint with type, signature, and size validation
- Filesystem/database rollback on failed persistence
- Page-aware PDF text extraction with PyMuPDF
- Controlled handling for corrupt, non-PDF, blank-page, and encrypted files
- Page-aware overlapping chunking with deterministic indexes
- Provider-neutral embedding abstraction with OpenAI as the first provider
- Schema-aligned 1536-dimension embedding validation
- Synchronous document ingestion orchestration from upload through persisted chunks
- Safe processing/failed/processed status transitions
- Document list and detail endpoints with public-safe metadata
- Document deletion with database cascade and local-file cleanup
- Grounded RAG prompt/context builder with source metadata separated from generated text
- Provider-neutral LLM generation abstraction using the OpenAI Responses API
- pgvector cosine-similarity retrieval with processed-document filtering
- Chat/RAG endpoint returning grounded answers with document/page sources
- Configurable retrieval-quality threshold that suppresses weak-context generation
- React + Vite + TypeScript frontend bootstrap with smoke tests
- Responsive document + chat application shell for desktop and mobile
- Centralized typed frontend API client for documents, uploads, deletion, and chat
- Live document sidebar with loading, empty, failure, retry, status, and timestamp states
- PDF upload interaction with client-side file filtering, pending state, API errors, and post-upload refresh
- Bounded automatic status refresh for uploaded/processing documents until ready or failed
- Confirmed document deletion with pending/error states and local list updates after success
- Reusable chat presentation for user/assistant messages, citations, composer, and empty state
- Live grounded chat flow through the RAG API with pending, cancellation, sequential-question, and failure states
- Deduplicated source chips with document/page traceability and long-filename handling
- Distinct chat UX for insufficient document context, no ready documents, offline failures, server failures, and temporary AI-service outages
- Keyboard-first and screen-reader-friendly interaction for chat, async states, upload, and document deletion
- Consolidated frontend regression suite with a deterministic `npm test` command and primary workflow coverage
- Predictable frontend error mapping for HTTP, validation, network, timeout, cancellation, and invalid responses
- Structured backend observability for uploads, ingestion, retrieval, provider latency, and application errors
- Repeatable RAG retrieval evaluation with synthetic PDFs, expected source pages, and unsupported-question thresholds
- Frontend API-base configuration validation
- Storage, upload, extraction, chunking, embedding, ingestion, document-read, deletion, RAG prompt, generation, retrieval, chat, and insufficient-context tests
- Initial project documentation

Planned next:

- End-to-end browser happy-path coverage
- Web CI and production build validation
- Production hardening, end-to-end tests, and deployment

## Target architecture

```text
PDF upload
    |
    v
FastAPI
    |
    v
Text extraction -> chunking -> embeddings
                           |
                           v
                 PostgreSQL + pgvector
                           |
User question -> embedding -> vector search
                           |
                           v
                     relevant chunks
                           |
                           v
                          LLM
                           |
                           v
                 answer + citations
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture and [PRD.md](PRD.md) for product requirements.

## Tech stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL 16
- pgvector
- PyMuPDF
- OpenAI embeddings
- OpenAI Responses API
- React 19
- Vite
- TypeScript
- Vitest + React Testing Library
- Docker / Docker Compose
- Alembic
- Pytest

The frontend is bootstrapped under `frontend/` and will be built out incrementally through the Web backlog.

## Run the backend and database with Docker Compose

From the repository root, with Docker Compose v2 installed:

```bash
# Optional: put POSTGRES_PASSWORD, OPENAI_API_KEY and LLM_MODEL in a root .env.
docker compose up --build --wait -d
curl -f http://localhost:8000/health
curl -f http://localhost:8000/health/database
```

The API image includes its Alembic migrations. Compose waits for PostgreSQL
to become healthy, then the API applies migrations before starting Uvicorn.
`postgres_data` preserves the database and `document_storage` preserves PDF
uploads across regular restarts and `docker compose down`. Never run
`docker compose down -v` unless you intend to delete those volumes.

Both published ports bind only to localhost. This is a **local development**
configuration with disposable default database credentials, not a public
deployment manifest. For real data, set a strong `POSTGRES_PASSWORD` in the
root `.env` (URL-encode special characters for the database connection string).
No paid AI API call is required to boot or check health; document ingestion and
chat still require a valid `OPENAI_API_KEY` and model.

```bash
bash scripts/smoke-compose.sh  # optional health/restart check on Linux/macOS
docker compose down            # stops services, retains volumes
```

To run the backend natively instead, follow the steps below and start
**only PostgreSQL** with `docker compose up -d postgres` so the container API
does not occupy port 8000.

## Local setup

### 1. Clone and enter the project

```bash
git clone https://github.com/LucasDiasRamos/ai-document-assistant.git
cd ai-document-assistant
```

### 2. Start PostgreSQL

```bash
docker compose up -d postgres
```

### 3. Create the backend environment

```bash
cd backend
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Copy `.env.example` to `backend/.env`, then set `LLM_MODEL` to a model available to your OpenAI API project before starting the application.

### 6. Configure the frontend

Use Node `20.19+` within the Node 20 line, or Node `22.12+`. Node 21 and Node 22.0–22.11 are intentionally not supported because Vite 8 excludes those runtimes.

From the repository root:

```bash
cd frontend
cp .env.example .env
npm install
```

The frontend uses a same-origin API path in development:

```env
VITE_API_BASE_URL=/api
```

Vite proxies `/api` requests to `http://localhost:8000`, so browser requests stay same-origin and do not require development CORS. Production may use either a same-origin root-relative path behind a reverse proxy or an absolute HTTP(S) API root such as `https://api.example.com/api`.

Invalid or missing API base values fail during frontend startup with a clear configuration error.

Run the frontend:

```bash
npm run dev
```

Run frontend tests:

```bash
npm run test:run
```

Create a production build:

```bash
npm run build
```

### 7. Apply database migrations

From `backend/`:

```bash
alembic upgrade head
```

This enables pgvector and creates the current persistence schema.

### 8. Run the API

From `backend/`:

```bash
uvicorn app.main:app --reload
```

Open:

- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- Database health: `http://localhost:8000/health/database`

## Backend pull-request CI

`.github/workflows/backend-ci.yml` validates backend changes on pull requests
and on pushes to `main` that affect backend code, Compose, or the workflow.

The `tests` job installs Python 3.12 dependencies, waits for a disposable
PostgreSQL 16 + pgvector service, applies Alembic migrations, then runs the
complete `pytest` suite. This includes database-backed retrieval tests that
otherwise skip when PostgreSQL is unavailable.

The `compose-smoke` job validates Compose syntax, builds the backend image,
starts PostgreSQL and the API, waits for health checks, then verifies HTTP
readiness and the expected Alembic revision.

Both jobs use throwaway CI-only database passwords and a dummy model name. They
do not need any paid AI API credentials, and provider requests in tests should
remain mocked. No production credentials or sensitive customer documents may
be added to workflow environment variables.

To reproduce the checks locally:

```bash
cd backend
alembic upgrade head
python -m pytest -q
cd ..
docker compose config --quiet
bash scripts/smoke-compose.sh
```

Docker Compose tests require a running Docker daemon and Docker Compose v2.

## Product goal

The initial version intentionally avoids a heavy RAG framework. The goal is to make ingestion, chunking, embeddings, retrieval, prompt construction, and citation handling explicit and easy to understand.

## License

A license has not been selected yet.


### Frontend tests

Run the full frontend regression suite once with:

```bash
cd frontend
npm test
```

Use `npm run test:watch` for local watch mode.


### RAG evaluation

Run the retrieval-quality fixtures without a paid generation provider:

```bash
cd backend
pytest tests/test_rag_evaluation.py -q
```

The always-on portion extracts and chunks the committed synthetic PDFs and checks expected page retrieval with deterministic test embeddings. When the configured PostgreSQL/pgvector test database is available, the same corpus also runs through the production ingestion and pgvector retrieval path.

## Security baseline for a public demo (API-25)

For a public environment set `APP_ENVIRONMENT=production` and
`CORS_ALLOWED_ORIGINS` to a JSON list of **exact HTTPS frontend origins**,
such as `["https://frontend.example.com"]`. Startup rejects missing,
wildcard or plain-HTTP production origins. The production application disables
Swagger, ReDoc, OpenAPI and debug traces.

The production API applies a lightweight in-process sliding-window limit to
anonymous `POST /api/chat` and `POST /api/documents` requests. Exceeded
requests return HTTP 429, the stable `rate_limited` code and
`Retry-After`. Quotas can be tuned with
`CHAT_REQUESTS_PER_MINUTE`, `UPLOAD_REQUESTS_PER_MINUTE` and
`RATE_LIMIT_WINDOW_SECONDS`. Existing PDF-size/type/signature constraints,
provider request timeouts, and safe API error envelopes are retained.
Upload filenames containing path separators or control characters are rejected.

**Important:** The rate limiter uses only the ASGI peer address, not
untrusted forwarded IP headers, and tracks limits per worker. Behind reverse
proxies or across multiple workers, implement a trusted ingress-level
distributed rate limiter and provider billing quotas. CORS is not access
control or authentication. This portfolio MVP has **shared anonymous
documents** and no tenant isolation; do not expose private PDFs or customer
data, and protect/seed a public demo with non-sensitive, disposable fixtures.
Configure credentials in hosting platform secrets, never in source or bundled
frontend code. For a production multi-tenant system, add authentication,
authorization, data isolation, and retention/deletion controls first.
