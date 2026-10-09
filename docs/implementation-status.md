# Implementation status

This document records the detailed implementation checklist from the original project README. It describes repository functionality, not a production deployment or externally verified service.

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
- Production API security baseline with exact-origin CORS, basic throttling, and safe upload filenames
- Automated backend and frontend GitHub Actions checks, with passing production frontend build
- Portfolio-facing README with quick start and honest demo status
- Initial project documentation

Planned next:

- End-to-end browser happy-path coverage
- Production deployment hardening, persistent public storage, and hosted demo deployment
