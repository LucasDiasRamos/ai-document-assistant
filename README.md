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
- Predictable frontend error mapping for HTTP, validation, network, timeout, cancellation, and invalid responses
- Frontend API-base configuration validation
- Storage, upload, extraction, chunking, embedding, ingestion, document-read, deletion, RAG prompt, generation, retrieval, chat, and insufficient-context tests
- Initial project documentation

Planned next:

- Document list/sidebar wired to the API
- Upload and delete workflows
- RAG evaluation fixtures and threshold calibration

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

## Local setup

### 1. Clone and enter the project

```bash
git clone https://github.com/LucasDiasRamos/ai-document-assistant.git
cd ai-document-assistant
```

### 2. Start PostgreSQL

```bash
docker compose up -d
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

## Product goal

The initial version intentionally avoids a heavy RAG framework. The goal is to make ingestion, chunking, embeddings, retrieval, prompt construction, and citation handling explicit and easy to understand.

## License

A license has not been selected yet.
