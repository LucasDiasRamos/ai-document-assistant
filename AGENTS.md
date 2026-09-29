# AGENTS.md

Repository-level instructions for coding agents and contributors working on AI Document Assistant.

## Mission

Build a portfolio-grade AI document question-answering application that demonstrates a clear and maintainable RAG implementation using FastAPI, PostgreSQL, pgvector, and an LLM provider.

## Product priorities

1. Correct document grounding
2. Source traceability
3. Simple architecture
4. Maintainable code
5. Good developer experience
6. Portfolio-quality documentation

## Engineering principles

### Prefer explicit code over framework magic

Do not add LangChain, LlamaIndex, or another orchestration framework unless there is a documented reason that materially improves the product.

The RAG pipeline should remain understandable:

```text
extract -> chunk -> embed -> store -> retrieve -> prompt -> generate -> cite
```

### Avoid overengineering

Do not introduce microservices, event brokers, Kubernetes, multiple databases, dedicated vector infrastructure, agent frameworks, or CQRS/event sourcing unless a future requirement clearly justifies them.

### Preserve traceability

Every retrievable chunk must preserve enough metadata to identify its source document and page.

## Repository layout

```text
backend/
  app/
    api/
      routes/
    core/
    models/
    schemas/
    services/
  tests/
frontend/
docs/
storage/
```

Route handlers should stay thin and delegate application behavior to services.

## Python standards

- Target Python 3.12-compatible syntax.
- Use type hints for public functions and important internals.
- Prefer small functions with clear responsibilities.
- Keep configuration in environment variables.
- Never commit credentials.
- Prefer FastAPI dependency injection for DB sessions.

## Database rules

- PostgreSQL is the source of truth for application metadata.
- pgvector stores embeddings in the MVP.
- Schema changes must use Alembic after migrations are introduced.
- Use intentional foreign keys and cascades.
- Do not hard-code embedding dimensionality in multiple places.

## RAG rules

### Ingestion
- Extract PDFs page by page.
- Preserve page numbers.
- Normalize text conservatively.
- Centralize chunking settings.
- Do not silently discard failed pages.

### Embeddings
- Keep provider-specific details behind a service boundary.
- Keep embedding model dimensions consistent with the DB schema.

### Retrieval
- Start with semantic top-k vector search.
- Do not add reranking or hybrid search before establishing a baseline.
- Retrieval results must preserve citation metadata.

### Generation
- Answers must use supplied document context.
- Unsupported questions must return a clear insufficient-context response.
- Never cite a source that was not part of retrieved context.

## File handling

- Validate supported file types.
- Never trust client filenames as internal storage paths.
- Generate safe unique storage names.
- Add upload-size limits before public deployment.
- Never commit user-uploaded documents under `storage/`.

## API conventions

- Product endpoints live under `/api`.
- Health endpoints stay at `/health` and `/health/database`.
- Use meaningful HTTP status codes.
- Return structured validation errors.
- Keep response models stable and documented in OpenAPI.

## Testing expectations

Priority areas:
1. chunking
2. PDF page attribution
3. persistence
4. vector retrieval
5. endpoint behavior
6. unsupported-question behavior
7. cascading document deletion

Avoid tests that call paid AI APIs by default. Provider calls should be mockable.

## Documentation

Update these files when scope or architecture changes:

- `README.md` — setup and public overview
- `ARCHITECTURE.md` — technical design
- `PRD.md` — product scope and requirements
- `AGENTS.md` — engineering/agent instructions

## Git workflow

Prefer focused branches:

```text
feat/document-models
feat/pdf-upload
feat/document-chunking
feat/vector-retrieval
feat/rag-chat
fix/pdf-page-metadata
```

Use conventional-style commits when practical.

Pull requests should explain what changed, why, how it was tested, relevant architectural decisions, and screenshots for UI work.

## Definition of done

A feature is done when:
- it meets the relevant PRD requirement;
- code is understandable and in the correct layer;
- errors are handled intentionally;
- important behavior is tested;
- secrets are not committed;
- documentation is updated when needed;
- the app still runs locally using documented setup steps.
