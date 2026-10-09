import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

const filename = "employee_handbook.pdf";
const knownQuestion = "How many remote work days are allowed per week?";
const deterministicAnswer =
  "The employee handbook includes the remote-work policy.";

const fixturePath = resolve(
  process.cwd(),
  "../backend/tests/fixtures/rag_eval/employee_handbook.pdf",
);

test("PDF upload, pgvector retrieval, grounded citation, and deletion", async ({
  page,
  request,
}) => {
  // This is NOT a mocked HTTP interface: Vite proxies /api to a live FastAPI
  // process backed by a disposable migrated PostgreSQL/pgvector database.
  // Only the embedding and generation providers are deterministic.
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "No searchable documents yet" }),
  ).toBeVisible();

  const pdf = await readFile(fixturePath);
  expect(pdf.subarray(0, 5).toString()).toBe("%PDF-");

  await page.getByLabel("Choose PDF to upload").setInputFiles({
    name: filename,
    mimeType: "application/pdf",
    buffer: pdf,
  });

  const documents = page.getByRole("list", { name: "Uploaded documents" });
  await expect(documents.getByText(filename)).toBeVisible();
  await expect(documents.getByText("Ready")).toBeVisible();

  const question = page.getByRole("textbox", {
    name: "Ask a question about your documents",
  });
  await expect(question).toBeEnabled();
  await question.fill(knownQuestion);
  await page.getByRole("button", { name: "Send question" }).click();

  await expect(page.getByText(deterministicAnswer)).toBeVisible();
  await expect(
    page.getByRole("listitem", { name: `${filename}, page 1` }),
  ).toBeVisible();

  await page.getByRole("button", { name: `Delete ${filename}` }).click();
  await expect(
    page.getByRole("group", { name: `Confirm deletion of ${filename}` }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Delete", exact: true }).click();

  await expect(
    page.getByRole("heading", { name: "No documents yet" }),
  ).toBeVisible();
  await expect(question).toBeDisabled();

  // Verify the real database read path after the destructive operation,
  // rather than relying only on the UI's optimistic local state.
  const afterDelete = await request.get("http://127.0.0.1:8000/api/documents");
  expect(afterDelete.ok()).toBeTruthy();
  expect((await afterDelete.json()).total).toBe(0);
});
