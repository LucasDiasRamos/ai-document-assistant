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
- Initial project documentation

Planned next:

- Safe PDF storage
- PDF upload endpoint
- PDF text extraction with page metadata
- Chunking
- Embedding generation
- pgvector similarity search
- RAG answer generation with source citations
- React frontend

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
- Docker / Docker Compose
- Alembic
- Pytest

The frontend and AI provider will be added in later milestones.

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

Copy `.env.example` to `backend/.env`.

### 6. Apply database migrations

From `backend/`:

```bash
alembic upgrade head
```

This enables pgvector and creates the current persistence schema.

### 7. Run the API

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
