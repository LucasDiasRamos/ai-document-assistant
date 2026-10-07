import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { ApiClient } from "./services/apiClient";
import type {
  ChatResponse,
  DocumentListResponse,
  DocumentUploadResponse,
} from "./types/api";

function readyDocument() {
  return {
    id: 1,
    original_filename: "portfolio-demo.pdf",
    status: "processed" as const,
    error_message: null,
    created_at: "2026-10-07T12:00:00Z",
    updated_at: "2026-10-07T12:01:00Z",
  };
}

describe("primary frontend workflow", () => {
  it("covers upload, readiness, grounded chat, citation, and delete", async () => {
    const document = readyDocument();

    const listDocuments = vi
      .fn<() => Promise<DocumentListResponse>>()
      .mockResolvedValueOnce({
        documents: [],
        total: 0,
      })
      .mockResolvedValue({
        documents: [document],
        total: 1,
      });

    const uploadDocument = vi
      .fn<() => Promise<DocumentUploadResponse>>()
      .mockResolvedValue(document);

    const deleteDocument = vi
      .fn<() => Promise<void>>()
      .mockResolvedValue();

    const sendChat = vi
      .fn<() => Promise<ChatResponse>>()
      .mockResolvedValue({
        answer: "The policy requires traceable grounded answers.",
        sources: [
          {
            document_id: 1,
            document: "portfolio-demo.pdf",
            page: 3,
          },
        ],
      });

    const client: ApiClient = {
      listDocuments,
      uploadDocument,
      deleteDocument,
      sendChat,
    };

    render(
      <App
        documentClient={client}
        chatClient={client}
      />,
    );

    expect(
      await screen.findByRole("heading", {
        name: "No searchable documents yet",
      }),
    ).toBeInTheDocument();

    const file = new File(
      ["%PDF-1.7 sample"],
      "portfolio-demo.pdf",
      {
        type: "application/pdf",
      },
    );

    fireEvent.change(
      screen.getByLabelText("Choose PDF to upload"),
      {
        target: { files: [file] },
      },
    );

    expect(
      await screen.findByText("portfolio-demo.pdf"),
    ).toBeInTheDocument();

    const questionInput = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });

    await waitFor(() => {
      expect(questionInput).toBeEnabled();
    });

    fireEvent.change(questionInput, {
      target: {
        value: "What does the policy require?",
      },
    });
    fireEvent.keyDown(questionInput, {
      key: "Enter",
      code: "Enter",
    });

    expect(
      await screen.findByText(
        "The policy requires traceable grounded answers.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("listitem", {
        name: "portfolio-demo.pdf, page 3",
      }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Delete portfolio-demo.pdf",
      }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Delete" }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "No documents yet",
      }),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("button", {
        name: "Delete portfolio-demo.pdf",
      }),
    ).not.toBeInTheDocument();

    expect(deleteDocument).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );

    expect(
      await screen.findByText(
        "No searchable documents available.",
      ),
    ).toBeInTheDocument();
    expect(questionInput).toBeDisabled();
  });
});
