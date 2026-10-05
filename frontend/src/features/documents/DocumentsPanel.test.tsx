import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  ApiClientError,
  type ApiClient,
} from "../../services/apiClient";
import type { DocumentSummary } from "../../types/api";
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
): ApiClient {
  return {
    listDocuments,
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    sendChat: vi.fn(),
  };
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
});
