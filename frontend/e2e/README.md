# Real browser E2E test (WEB-15)

This Playwright suite runs real Chromium against the Vite/React application
and a **real FastAPI + migrated PostgreSQL/pgvector** backend. It uploads the
committed synthetic three-page PDF, checks the processed status, submits a
known question, verifies an answer with a page-1 citation, deletes the file,
and queries the backend to ensure the database record was removed.

Only the paid **embedding and text-generation providers** are deterministic.
The test does not exercise an external OpenAI API; it does exercise real HTTP,
multipart upload, PDF parsing, chunk persistence, vector retrieval and deletion.

## Local execution

1. Run PostgreSQL/pgvector: `docker compose up -d postgres`.
2. Create the backend virtual environment, install
   `backend/requirements.txt`, and configure `DATABASE_URL`, `LLM_MODEL`
   and `STORAGE_ROOT` for a **throwaway database and directory**.
3. From `backend/`, run `alembic upgrade head`, then start the
   test-only service:

   ```bash
   ENABLE_DETERMINISTIC_E2E=1 uvicorn e2e_app:app --host 127.0.0.1 --port 8000
   ```

4. From `frontend/`, run:

   ```bash
   npm install
   npx playwright install chromium
   npm run test:e2e
   ```

The runner starts and stops the Vite dev server itself. It runs the flow in
desktop and mobile Chromium with a single worker because both cases reuse
the disposable database. Never use the E2E entrypoint against customer data
or on a public server: the fake provider entrypoint requires an explicit
`ENABLE_DETERMINISTIC_E2E=1` guard and development mode.

GitHub Actions builds this environment from scratch and stores browser
traces/screenshots after failures.
