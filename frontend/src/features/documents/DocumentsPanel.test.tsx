import { StrictMode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  ApiClientError,
  type ApiClient,
} from "../../services/apiClient";
import type {
  DocumentSummary,
  DocumentUploadResponse,
} from "../../types/api";
import { DocumentsPanel } from "./DocumentsPanel";

function documentFixture(
  overrides: Partial<DocumentSummary> = {},
): DocumentSummary {
  return {
    id: 1,
    original_filename: "manual.pdf",
    status: "processed",
    error_message: null,
    created_at: "2026-10-03T12:00:00Z",
    updated_at: "2026-10-03T12:01:00Z",
    ...overrides,
  };
}

function clientWithList(
  listDocuments: ApiClient["listDocuments"],
  uploadDocument: ApiClient["uploadDocument"] = vi.fn(),
): ApiClient {
  return {
    listDocuments,
    uploadDocument,
    deleteDocument: vi.fn(),
    sendChat: vi.fn(),
  };
}

function pdfFile(name = "guide.pdf"): File {
  return new File(["%PDF-1.7"], name, {
    type: "application/pdf",
  });
}

describe("DocumentsPanel", () => {
  it("renders the empty state when no documents exist", async () => {
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [],
        total: 0,
      }),
    );

    render(<DocumentsPanel client={client} />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading documents",
    );

    expect(
      await screen.findByRole("heading", { name: "No documents yet" }),
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("0 documents uploaded"),
    ).toHaveTextContent("0");
  });

  it("renders one processed document", async () => {
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [documentFixture()],
        total: 1,
      }),
    );

    render(<DocumentsPanel client={client} />);

    expect(await screen.findByText("manual.pdf")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText(/Uploaded Oct 3/)).toBeInTheDocument();
    expect(
      screen.getByLabelText("1 document uploaded"),
    ).toHaveTextContent("1");
  });

  it("renders multiple document processing states", async () => {
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [
          documentFixture({
            id: 1,
            original_filename: "ready.pdf",
            status: "processed",
          }),
          documentFixture({
            id: 2,
            original_filename: "processing.pdf",
            status: "processing",
          }),
          documentFixture({
            id: 3,
            original_filename: "uploaded.pdf",
            status: "uploaded",
          }),
          documentFixture({
            id: 4,
            original_filename: "failed.pdf",
            status: "failed",
            error_message: "Document processing failed",
          }),
        ],
        total: 4,
      }),
    );

    render(<DocumentsPanel client={client} />);

    expect(await screen.findByText("ready.pdf")).toBeInTheDocument();
    expect(screen.getByText("processing.pdf")).toBeInTheDocument();
    expect(screen.getByText("uploaded.pdf")).toBeInTheDocument();
    expect(screen.getByText("failed.pdf")).toBeInTheDocument();

    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Processing")).toBeInTheDocument();
    expect(screen.getByText("Uploaded")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(
      screen.getByText("Document processing failed"),
    ).toBeInTheDocument();
  });

  it("shows an API error and retries successfully", async () => {
    const listDocuments = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiClientError("Unable to reach the API", {
          kind: "network",
        }),
      )
      .mockResolvedValueOnce({
        documents: [
          documentFixture({
            original_filename: "recovered.pdf",
          }),
        ],
        total: 1,
      });

    const client = clientWithList(listDocuments);

    render(<DocumentsPanel client={client} />);

    expect(
      await screen.findByRole("heading", {
        name: "Could not load documents",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Unable to reach the API")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("recovered.pdf")).toBeInTheDocument();

    await waitFor(() => {
      expect(listDocuments).toHaveBeenCalledTimes(2);
    });
  });

  it("uploads a valid PDF and refreshes the document list", async () => {
    const uploaded = documentFixture({
      id: 8,
      original_filename: "guide.pdf",
    });
    const listDocuments = vi
      .fn()
      .mockResolvedValueOnce({
        documents: [],
        total: 0,
      })
      .mockResolvedValueOnce({
        documents: [uploaded],
        total: 1,
      });
    const uploadDocument = vi
      .fn()
      .mockResolvedValue(uploaded as DocumentUploadResponse);
    const client = clientWithList(listDocuments, uploadDocument);

    render(<DocumentsPanel client={client} />);

    await screen.findByRole("heading", { name: "No documents yet" });

    const input = screen.getByLabelText("Choose PDF to upload");
    const file = pdfFile();

    fireEvent.change(input, {
      target: { files: [file] },
    });

    await waitFor(() => {
      expect(uploadDocument).toHaveBeenCalledTimes(1);
    });

    expect(uploadDocument).toHaveBeenCalledWith(
      file,
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );

    expect(await screen.findByText("guide.pdf")).toBeInTheDocument();
    expect(listDocuments).toHaveBeenCalledTimes(2);
  });

  it("rejects an obvious non-PDF selection before upload", async () => {
    const uploadDocument = vi.fn();
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [],
        total: 0,
      }),
      uploadDocument,
    );

    render(<DocumentsPanel client={client} />);

    await screen.findByRole("heading", { name: "No documents yet" });

    fireEvent.change(screen.getByLabelText("Choose PDF to upload"), {
      target: {
        files: [
          new File(["hello"], "notes.txt", {
            type: "text/plain",
          }),
        ],
      },
    });

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("Please select a PDF file.");
    expect(uploadDocument).not.toHaveBeenCalled();
  });

  it("shows a server validation error after upload rejection", async () => {
    const uploadDocument = vi.fn().mockRejectedValue(
      new ApiClientError("The uploaded file is not a valid PDF", {
        kind: "http",
        status: 400,
      }),
    );
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [],
        total: 0,
      }),
      uploadDocument,
    );

    render(<DocumentsPanel client={client} />);
    await screen.findByRole("heading", { name: "No documents yet" });

    fireEvent.change(screen.getByLabelText("Choose PDF to upload"), {
      target: { files: [pdfFile("invalid.pdf")] },
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The uploaded file is not a valid PDF",
    );
    expect(
      screen.getByRole("button", { name: "Upload PDF" }),
    ).toBeEnabled();
  });

  it("shows a predictable network failure during upload", async () => {
    const uploadDocument = vi.fn().mockRejectedValue(
      new ApiClientError("Unable to reach the API", {
        kind: "network",
      }),
    );
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [],
        total: 0,
      }),
      uploadDocument,
    );

    render(<DocumentsPanel client={client} />);
    await screen.findByRole("heading", { name: "No documents yet" });

    fireEvent.change(screen.getByLabelText("Choose PDF to upload"), {
      target: { files: [pdfFile()] },
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to reach the API",
    );
  });

  it("disables upload while the active request is pending", async () => {
    let resolveUpload:
      | ((value: DocumentUploadResponse) => void)
      | undefined;

    const uploadDocument = vi.fn(
      () =>
        new Promise<DocumentUploadResponse>((resolve) => {
          resolveUpload = resolve;
        }),
    );
    const listDocuments = vi.fn().mockResolvedValue({
      documents: [],
      total: 0,
    });
    const client = clientWithList(listDocuments, uploadDocument);

    render(<DocumentsPanel client={client} />);
    await screen.findByRole("heading", { name: "No documents yet" });

    fireEvent.change(screen.getByLabelText("Choose PDF to upload"), {
      target: { files: [pdfFile()] },
    });

    const pendingButton = await screen.findByRole("button", {
      name: "Uploading…",
    });

    expect(pendingButton).toBeDisabled();
    expect(
      screen.getByLabelText("Choose PDF to upload"),
    ).toBeDisabled();
    expect(uploadDocument).toHaveBeenCalledTimes(1);

    resolveUpload?.(
      documentFixture({
        id: 9,
        original_filename: "guide.pdf",
      }),
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Upload PDF" }),
      ).toBeEnabled();
    });
  });

  it("completes uploads correctly under React StrictMode", async () => {
    const uploaded = documentFixture({
      id: 12,
      original_filename: "strict-mode.pdf",
    });
    const listDocuments = vi.fn().mockResolvedValue({
      documents: [uploaded],
      total: 1,
    });
    const uploadDocument = vi
      .fn()
      .mockResolvedValue(uploaded as DocumentUploadResponse);
    const client = clientWithList(listDocuments, uploadDocument);

    render(
      <StrictMode>
        <DocumentsPanel client={client} />
      </StrictMode>,
    );

    await screen.findByText("strict-mode.pdf");

    fireEvent.change(screen.getByLabelText("Choose PDF to upload"), {
      target: { files: [pdfFile("strict-mode.pdf")] },
    });

    await waitFor(() => {
      expect(uploadDocument).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Upload PDF" }),
      ).toBeEnabled();
    });

    expect(listDocuments.mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it("cancels the active list request on unmount", () => {
    let receivedSignal: AbortSignal | undefined;

    const client = clientWithList(
      vi.fn((_limit, options) => {
        receivedSignal = options?.signal;

        return new Promise<never>(() => undefined);
      }),
    );

    const { unmount } = render(<DocumentsPanel client={client} />);

    expect(receivedSignal?.aborted).toBe(false);

    unmount();

    expect(receivedSignal?.aborted).toBe(true);
  });

  it("cancels an active upload request on unmount", async () => {
    let uploadSignal: AbortSignal | undefined;

    const uploadDocument = vi.fn(
      (_file, options) => {
        uploadSignal = options?.signal;

        return new Promise<DocumentUploadResponse>(() => undefined);
      },
    );
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [],
        total: 0,
      }),
      uploadDocument,
    );

    const { unmount } = render(<DocumentsPanel client={client} />);
    await screen.findByRole("heading", { name: "No documents yet" });

    fireEvent.change(screen.getByLabelText("Choose PDF to upload"), {
      target: { files: [pdfFile()] },
    });

    await waitFor(() => {
      expect(uploadSignal).toBeDefined();
    });

    expect(uploadSignal?.aborted).toBe(false);

    unmount();

    expect(uploadSignal?.aborted).toBe(true);
  });
});
