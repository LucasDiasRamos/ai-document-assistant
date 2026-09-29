# Product Requirements Document — AI Document Assistant

## 1. Product summary

AI Document Assistant is a web application that lets users upload PDF documents and ask natural-language questions about their contents.

The system uses Retrieval-Augmented Generation (RAG) to retrieve relevant passages before generating an answer. Answers must be grounded in uploaded documents and include source attribution by document and page.

## 2. Problem

Important business and technical information is often buried inside manuals, policies, contracts, procedures, and reports.

Users frequently need to search large PDFs manually, inspect multiple files, remember internal terminology, and validate whether an answer is actually supported by the source.

## 3. Product objective

Provide a simple document Q&A experience where a user uploads a PDF, asks a question, and receives a useful answer grounded in retrieved document content with traceable sources.

## 4. Portfolio objective

The project should demonstrate production-relevant engineering capabilities:

- Python backend development
- FastAPI and REST API design
- PostgreSQL
- pgvector
- document processing
- embeddings
- vector retrieval
- RAG
- LLM integration
- source traceability
- Docker
- testing
- technical documentation

## 5. Target users

- small businesses with internal documentation
- operations and support teams
- technical teams
- professionals working with contracts, manuals, policies, and reports
- prospective freelance clients evaluating similar AI automation work

## 6. Example use cases

### Manual lookup
Upload an equipment manual and ask: “What is the warranty period?”

### Policy lookup
Upload an internal policy and ask: “What is the cancellation procedure?”

### Report summary
Upload a report and ask: “What are the main findings?”

### Missing information
Ask a question not answered by the uploaded documents. The expected behavior is to state that the information was not found instead of inventing an answer.

## 7. MVP scope

### Must have
- PDF upload
- persistent document metadata
- local file storage for development
- page-preserving text extraction
- chunking with overlap
- embedding generation
- vector storage with pgvector
- semantic retrieval
- question endpoint
- grounded LLM response
- document/page citations
- document listing
- document deletion
- OpenAPI/Swagger docs
- Dockerized PostgreSQL
- automated tests for critical components

### Should have
- conversation history
- response streaming
- basic frontend
- processing status
- user-friendly errors
- configurable chunk/retrieval parameters

### Could have
- DOCX/TXT support
- multiple knowledge bases
- document preview
- source highlighting
- authentication
- multiple users
- usage metrics
- cloud object storage
- hybrid search
- reranking

### Won't have in the first MVP
- billing
- multi-tenant SaaS architecture
- fine-tuning
- autonomous agents
- OCR pipeline
- enterprise permissions
- multiple vector databases

## 8. Functional requirements

### FR-01 — API health
`GET /health` must return HTTP 200 and `{"status":"ok"}`.

### FR-02 — Database health
`GET /health/database` must return HTTP 200 when PostgreSQL is reachable.

### FR-03 — Upload PDF
The system must validate uploads, generate a safe internal filename, persist metadata, store the file, and process the document.

### FR-04 — Extract PDF text
Text must be extracted page by page with page attribution preserved.

### FR-05 — Chunk document text
Extracted content must be transformed into overlapping chunks suitable for semantic retrieval.

### FR-06 — Generate embeddings
The system must create an embedding for each searchable chunk.

### FR-07 — Store vectors
Chunk embeddings must be stored with pgvector.

### FR-08 — Retrieve relevant context
Given a user question, the system must run semantic similarity retrieval and return the most relevant chunks.

### FR-09 — Generate grounded answer
The answer must use retrieved context. If there is insufficient context, the system should say so.

### FR-10 — Cite sources
Responses must include the original document name and page number for supporting context.

### FR-11 — List documents
Users must be able to list uploaded documents and processing state.

### FR-12 — Delete document
Users must be able to delete a document and its associated chunks/vectors.

## 9. Non-functional requirements

### Maintainability
Business logic belongs in services, not directly in route handlers.

### Observability
Errors must include enough context for troubleshooting without logging secrets.

### Security
- never commit API keys
- validate uploads
- never trust client file paths
- use parameterized database access

### Portability
The MVP must run locally with Python and Docker.

### Reliability
Failed processing must expose a visible failure state.

## 10. Initial API contract

```http
GET /health
GET /health/database
POST /api/documents
GET /api/documents
DELETE /api/documents/{document_id}
POST /api/chat
```

Example chat request:

```json
{
  "question": "What is the warranty period?"
}
```

Example response:

```json
{
  "answer": "The warranty period is 12 months.",
  "sources": [
    {
      "document": "manual.pdf",
      "page": 17
    }
  ]
}
```

## 11. Success criteria for the portfolio MVP

A reviewer must be able to:
1. clone the repository;
2. start infrastructure;
3. run the API;
4. upload a PDF;
5. ask a supported question;
6. receive a grounded answer;
7. see the correct source document/page;
8. ask an unsupported question and receive an appropriate not-found response;
9. understand the architecture from repository documentation.

## 12. Milestones

### M0 — Bootstrap
FastAPI, configuration, SQLAlchemy, PostgreSQL + pgvector, health endpoints, and docs.

### M1 — Persistence
Document and DocumentChunk models, Alembic, migrations, CRUD foundations.

### M2 — Document ingestion
Upload, safe storage, PDF extraction, page metadata, chunking.

### M3 — Embeddings
Provider interface, vector column, embedding persistence.

### M4 — Retrieval
Question embedding, pgvector similarity search, top-k retrieval, tests.

### M5 — Generation
LLM provider abstraction, grounded prompt, answer endpoint, citations.

### M6 — Frontend
Document sidebar, upload interaction, chat UI, citation rendering.

### M7 — Portfolio hardening
Tests, screenshots, demo video, deploy, polished README, diagrams, sample docs.
