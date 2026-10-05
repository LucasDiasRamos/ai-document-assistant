import { StrictMode } from "react";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiClientError,
  type ApiClient,
} from "../../services/apiClient";
import type {
  DocumentSummary,
  DocumentUploadResponse,
} from "../../types/api";
import {
  DocumentsPanel,
  MAX_STATUS_POLL_ATTEMPTS,
  STATUS_POLL_INTERVAL_MS,
} from "./DocumentsPanel";

afterEach(() => {
  vi.useRealTimers();
});

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
  deleteDocument: ApiClient["deleteDocument"] = vi.fn(),
): ApiClient {
  return {
    listDocuments,
    uploadDocument,
    deleteDocument,
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

  it("polls uploaded to processing to processed and then stops", async () => {
    vi.useFakeTimers();

    const uploaded = documentFixture({
      original_filename: "pipeline.pdf",
      status: "uploaded",
    });
    const processing = documentFixture({
      original_filename: "pipeline.pdf",
      status: "processing",
    });
    const processed = documentFixture({
      original_filename: "pipeline.pdf",
      status: "processed",
    });

    const listDocuments = vi
      .fn()
      .mockResolvedValueOnce({
        documents: [uploaded],
        total: 1,
      })
      .mockResolvedValueOnce({
        documents: [processing],
        total: 1,
      })
      .mockResolvedValueOnce({
        documents: [processed],
        total: 1,
      });

    const client = clientWithList(listDocuments);

    render(<DocumentsPanel client={client} />);

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText("Uploaded")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(STATUS_POLL_INTERVAL_MS);
    });

    expect(screen.getByText("Processing")).toBeInTheDocument();
    expect(listDocuments).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(STATUS_POLL_INTERVAL_MS);
    });

    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(listDocuments).toHaveBeenCalledTimes(3);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(STATUS_POLL_INTERVAL_MS * 3);
    });

    expect(listDocuments).toHaveBeenCalledTimes(3);
  });

  it("polls processing to failed and stops at the terminal state", async () => {
    vi.useFakeTimers();

    const processing = documentFixture({
      original_filename: "broken.pdf",
      status: "processing",
    });
    const failed = documentFixture({
      original_filename: "broken.pdf",
      status: "failed",
      error_message: "Document processing failed",
    });

    const listDocuments = vi
      .fn()
      .mockResolvedValueOnce({
        documents: [processing],
        total: 1,
      })
      .mockResolvedValueOnce({
        documents: [failed],
        total: 1,
      });

    const client = clientWithList(listDocuments);

    render(<DocumentsPanel client={client} />);

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText("Processing")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(STATUS_POLL_INTERVAL_MS);
    });

    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(
      screen.getByText("Document processing failed"),
    ).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(STATUS_POLL_INTERVAL_MS * 3);
    });

    expect(listDocuments).toHaveBeenCalledTimes(2);
  });

  it("caps polling when a document never leaves a transitional state", async () => {
    vi.useFakeTimers();

    const processing = documentFixture({
      status: "processing",
    });

    const listDocuments = vi.fn().mockResolvedValue({
      documents: [processing],
      total: 1,
    });

    const client = clientWithList(listDocuments);

    render(<DocumentsPanel client={client} />);

    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(listDocuments).toHaveBeenCalledTimes(
      1 + MAX_STATUS_POLL_ATTEMPTS,
    );
    expect(vi.getTimerCount()).toBe(0);
  });

  it("aborts an active status poll when the component unmounts", async () => {
    vi.useFakeTimers();

    let pollSignal: AbortSignal | undefined;
    const processing = documentFixture({
      status: "processing",
    });

    const listDocuments = vi
      .fn()
      .mockResolvedValueOnce({
        documents: [processing],
        total: 1,
      })
      .mockImplementationOnce((_limit, options) => {
        pollSignal = options?.signal;

        return new Promise<never>(() => undefined);
      });

    const client = clientWithList(listDocuments);
    const { unmount } = render(<DocumentsPanel client={client} />);

    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(STATUS_POLL_INTERVAL_MS);
    });

    expect(pollSignal).toBeDefined();
    expect(pollSignal?.aborted).toBe(false);

    unmount();

    expect(pollSignal?.aborted).toBe(true);
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

  it("cancels document deletion confirmation without calling the API", async () => {
    const deleteDocument = vi.fn();
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [documentFixture()],
        total: 1,
      }),
      vi.fn(),
      deleteDocument,
    );

    render(<DocumentsPanel client={client} />);

    await screen.findByText("manual.pdf");

    fireEvent.click(
      screen.getByRole("button", { name: "Delete manual.pdf" }),
    );

    expect(
      screen.getByRole("group", {
        name: "Confirm deletion of manual.pdf",
      }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(
      screen.queryByRole("group", {
        name: "Confirm deletion of manual.pdf",
      }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("manual.pdf")).toBeInTheDocument();
    expect(deleteDocument).not.toHaveBeenCalled();
  });

  it("removes a document only after successful deletion", async () => {
    let resolveDelete: (() => void) | undefined;
    const deleteDocument = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveDelete = resolve;
        }),
    );
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [documentFixture()],
        total: 1,
      }),
      vi.fn(),
      deleteDocument,
    );

    render(<DocumentsPanel client={client} />);

    await screen.findByText("manual.pdf");

    fireEvent.click(
      screen.getByRole("button", { name: "Delete manual.pdf" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(deleteDocument).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
    expect(screen.getByText("manual.pdf")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Deleting…" }),
    ).toBeDisabled();

    resolveDelete?.();

    expect(
      await screen.findByRole("heading", { name: "No documents yet" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("manual.pdf")).not.toBeInTheDocument();
    expect(
      screen.getByLabelText("0 documents uploaded"),
    ).toHaveTextContent("0");
  });

  it("retains the document and shows an error when deletion fails", async () => {
    const deleteDocument = vi.fn().mockRejectedValue(
      new ApiClientError("Unable to delete document", {
        kind: "network",
      }),
    );
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [documentFixture()],
        total: 1,
      }),
      vi.fn(),
      deleteDocument,
    );

    render(<DocumentsPanel client={client} />);

    await screen.findByText("manual.pdf");

    fireEvent.click(
      screen.getByRole("button", { name: "Delete manual.pdf" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to delete document",
    );
    expect(screen.getByText("manual.pdf")).toBeInTheDocument();
    expect(
      screen.getByRole("group", {
        name: "Confirm deletion of manual.pdf",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete" }),
    ).toBeEnabled();
  });

  it("prevents repeated deletion while a request is pending", async () => {
    const first = documentFixture({
      id: 1,
      original_filename: "first.pdf",
    });
    const second = documentFixture({
      id: 2,
      original_filename: "second.pdf",
    });
    const deleteDocument = vi.fn(
      () => new Promise<void>(() => undefined),
    );
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [first, second],
        total: 2,
      }),
      vi.fn(),
      deleteDocument,
    );

    render(<DocumentsPanel client={client} />);

    await screen.findByText("first.pdf");

    fireEvent.click(
      screen.getByRole("button", { name: "Delete first.pdf" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(
      screen.getByRole("button", { name: "Deleting…" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Delete second.pdf" }),
    ).toBeDisabled();
    expect(deleteDocument).toHaveBeenCalledTimes(1);
  });

  it("aborts an active deletion when the component unmounts", async () => {
    let deleteSignal: AbortSignal | undefined;
    const deleteDocument = vi.fn((_documentId, options) => {
      deleteSignal = options?.signal;

      return new Promise<void>(() => undefined);
    });
    const client = clientWithList(
      vi.fn().mockResolvedValue({
        documents: [documentFixture()],
        total: 1,
      }),
      vi.fn(),
      deleteDocument,
    );

    const { unmount } = render(<DocumentsPanel client={client} />);

    await screen.findByText("manual.pdf");

    fireEvent.click(
      screen.getByRole("button", { name: "Delete manual.pdf" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(deleteSignal).toBeDefined();
    });

    expect(deleteSignal?.aborted).toBe(false);

    unmount();

    expect(deleteSignal?.aborted).toBe(true);
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
