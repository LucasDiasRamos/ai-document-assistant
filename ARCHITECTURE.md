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
Frontend (React/Vite later)
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

### FastAPI
Exposes REST endpoints, validates requests/responses, coordinates services, and exposes health checks.

Planned endpoints:
```text
GET  /health
GET  /health/database
POST /api/documents
GET  /api/documents
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
Extracts PDF text page by page so page attribution can be preserved.

### Embedding service
Converts text into vectors behind a replaceable provider boundary.

### Retrieval service
Embeds the user question, queries pgvector, ranks relevant chunks, and returns top-k chunks with source metadata.

### LLM service
Builds the grounded prompt, sends retrieved context to the selected LLM, and returns an answer constrained to document context.

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
2. Backend validates the file.
3. File is stored locally for the MVP.
4. Document record is created.
5. PyMuPDF extracts text page by page.
6. Text is split into overlapping chunks.
7. Each chunk receives metadata.
8. Embeddings are generated.
9. Chunks and vectors are persisted in PostgreSQL.
10. Document status becomes processed.

Important metadata: document ID, original filename, page number, and chunk index.

## 7. Query flow

1. User asks a question.
2. Question is converted to an embedding.
3. pgvector searches for nearest chunks.
4. Top-k chunks are selected.
5. Context is assembled with document/page metadata.
6. LLM receives system rules, context, and question.
7. Response is generated.
8. API returns answer and source references.

## 8. Chunking strategy

Initial strategy:
- approximately 800 tokens per chunk;
- approximately 100-150 tokens overlap;
- preserve page attribution;
- centralize chunking parameters.

## 9. Retrieval strategy

Initial retrieval uses semantic vector similarity with roughly top-5 chunks and no reranker. Hybrid search, reranking, query rewriting, and metadata filtering are future options only if evaluation justifies them.

## 10. Grounding rules

The system prompt must:
- answer from supplied document context;
- state when information is absent;
- avoid unsupported claims;
- return sources whenever context is used.

## 11. Configuration

Current variables:
```text
APP_NAME
DATABASE_URL
STORAGE_ROOT
```

Future variables may include `LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDING_MODEL`, provider API keys, `CHUNK_SIZE`, `CHUNK_OVERLAP`, and `RETRIEVAL_TOP_K`. The embedding vector dimension is intentionally schema-owned rather than runtime-configurable; changing it requires a database migration and a matching ORM update.

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
