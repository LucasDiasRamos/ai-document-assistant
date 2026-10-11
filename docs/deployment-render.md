# API-26 — Render backend deployment runbook

**Status: configuration prepared; no external service created.** The Blueprint
in [`render.yaml`](../render.yaml) is an *optional paid* reference deployment.
It provisions a single Docker web service, managed PostgreSQL 16 with
`pgvector`, a persistent source-PDF disk, and a private database connection.

This is **not** a production-ready multi-user system. The MVP has no login,
tenant isolation, fine-grained permissions, document retention policy or
provider-spend control. Its anonymous document endpoints are shared. Deploy
only for a controlled portfolio demonstration with disposable, non-sensitive
test PDFs, an additional access restriction at the hosting edge, and provider
billing alerts/quotas. CORS is not an authentication mechanism. Do not
put client, employee, student, or customer data in this demo.

## 1. Review cost and platform constraints

The Blueprint specifies **paid** resources: a Render Starter web service
with a 1 GB persistent disk and a managed PostgreSQL database with dedicated
compute/storage. Verify Render's live pricing and confirm costs **before**
importing the Blueprint. It deliberately sets `autoDeployTrigger: off` and
one service instance. A persistent Render disk prevents horizontal scaling;
the application also uses a per-process anonymous rate limiter. This is
suited only to a small controlled demo, not general public usage.

The disk is mounted at `/app/storage`, matching `STORAGE_ROOT` and the
absolute source-file paths persisted in PostgreSQL. Keep this path stable.
Only this mounted directory survives deploys/restarts; never move files to a
container's ephemeral filesystem. Configure backups for **both** PostgreSQL
and source PDFs. Disk snapshots are not a replacement for testing restores.

## 2. Import the Blueprint (manual user action)

1. Merge the API-26 PR, after code review and green CI.
2. In a Render account, create a Blueprint from the GitHub repository's
   `main` branch and the root `render.yaml`.
3. Review the named resources, selected region, paid plans and storage sizes.
   Do not click the final deploy/approve control until budget and public
   access restrictions are accepted.
4. Supply the secret variables prompted by the Render Blueprint:
   - `OPENAI_API_KEY`: generated and scoped via OpenAI's API dashboard, with
     strict provider budget monitoring;
   - `CORS_ALLOWED_ORIGINS`: a **JSON list** of exact, HTTPS frontend origins,
     e.g. `["https://your-frontend.example"]`. The frontend origin must be
     selected before the production API can start successfully.
5. The Blueprint references the managed database's private
   `connectionString`. The backend automatically converts Render's
   `postgresql://` URL to the `postgresql+psycopg://` driver expected by
   SQLAlchemy. Do not copy the URL to Git.
6. Confirm `APP_ENVIRONMENT=production`, `STORAGE_ROOT=/app/storage`, and
   `PORT=10000`. Keep the service protected against untrusted traffic.
7. Trigger a manual deploy. The Docker entrypoint applies Alembic migrations
   (including `CREATE EXTENSION vector`) before Uvicorn starts. A failure in
   migration or required configuration prevents the service from starting.

There is no default public frontend origin, no default API key, and no
hard-coded live deployment URL. The production FastAPI docs/schema are
disabled. Render should terminate HTTPS at its ingress.

## 3. Validate HTTPS, database and persistence

Once the external HTTPS URL and access restrictions are configured, run:

```bash
bash scripts/check-deployed-api.sh https://your-api.example
```

The script checks `/health` and `/health/database`. It refuses HTTP URLs
to avoid unintentionally testing a non-TLS public endpoint. When platform
access protection is enabled, validate through the authorized channel rather
than exposing credentials or bypassing the protection.

For the full, potentially **billable** application smoke test, use only a
small synthetic PDF and authorized access:

1. From the deployed frontend, upload the synthetic
   `backend/tests/fixtures/rag_eval/employee_handbook.pdf`.
2. Confirm the document becomes `processed` in the list.
3. Ask: "How many remote work days are allowed per week?"
4. Confirm a substantive answer and an `employee_handbook.pdf` page-1
   citation. Real AI answers are nondeterministic; inspect citation relevance.
5. Restart/redeploy the backend **without deleting the disk**.
6. Confirm the document remains available and that the PDF still exists under
   `/app/storage`. Repeat retrieval; verify the document ID stays unchanged.
7. Delete the sample document, verify it disappears, and check for orphan
   storage files. Stop the demo if any check fails.

Do not mark API-26 **Done** until the live HTTPS, end-to-end, persistence and
restart checks have passed. The existing Playwright CI covers a local stack
with deterministic providers, not a remotely deployed OpenAI integration.

## 4. Operational constraints and next steps

- Uploaded PDFs are kept on a persistent, single-instance disk. Moving to a
  multi-instance app requires an object-storage abstraction (e.g. S3) and
  consistent metadata migration, not just changing `STORAGE_ROOT`.
- Rate limits are local to the application process and use the direct
  network peer IP, which may be the hosting proxy. Configure trusted
  edge/ingress throttling and a sensible AI API budget before any public use.
- Only one app instance runs migrations at boot; coordinate migrations
  separately before adding horizontally scaled instances.
- HTTPS alone does not prevent anonymous uploads, deletions or paid AI usage.
  Implement real authentication and tenant isolation before public customer
  usage. At a minimum, put a controlled demo behind an edge access gateway.
- Record actual service URLs and verification results after the deployment.
  Do not advertise a hosted demo or mark API-26 complete on the basis of this
  Blueprint alone.

References:
- [Render Blueprint specification](https://render.com/docs/blueprint-spec)
- [Render pgvector support](https://render.com/docs/postgresql-extensions)
- [Render persistent disk behavior](https://render.com/docs/disks)
