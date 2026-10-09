import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { App } from "./App";
import type { ApiClient } from "./services/apiClient";

function createApiClient(): ApiClient {
  return {
    listDocuments: vi.fn().mockResolvedValue({
      documents: [],
      total: 0,
    }),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    sendChat: vi.fn(),
  };
}

describe("App", () => {
  it("renders the document and chat workspace", async () => {
    const client = createApiClient();

    render(
      <App
        documentClient={client}
        chatClient={client}
      />,
    );

    expect(
      screen.getByText("AI Document Assistant"),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", { name: "Documents" }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("region", { name: "How it works" }),
    ).toHaveTextContent("Ask questions. See the evidence.");

    expect(screen.getByText("Upload a PDF", { selector: "li" })).toBeInTheDocument();
    expect(screen.getByText("Check the source")).toBeInTheDocument();

    expect(
      screen.getByRole("heading", { name: "Ask your documents" }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Upload PDF" }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("textbox", {
        name: "Ask a question about your documents",
      }),
    ).toBeInTheDocument();

    expect(
      await screen.findByRole("heading", { name: "No documents yet" }),
    ).toBeInTheDocument();
  });

  it("exposes a keyboard skip link to the chat region", async () => {
    const client = createApiClient();

    render(
      <App
        documentClient={client}
        chatClient={client}
      />,
    );

    expect(
      screen.getByRole("link", { name: "Skip to chat" }),
    ).toHaveAttribute("href", "#main-content");

    expect(screen.getByRole("main")).toHaveAttribute(
      "id",
      "main-content",
    );

    expect(
      await screen.findByRole("heading", { name: "No documents yet" }),
    ).toBeInTheDocument();
  });

  it("guides the user when the knowledge base has no ready documents", async () => {
    const client = createApiClient();

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

    expect(
      screen.getByRole("textbox", {
        name: "Ask a question about your documents",
      }),
    ).toBeDisabled();
  });

  it("enables chat when at least one document is ready", async () => {
    const client = createApiClient();
    client.listDocuments = vi.fn().mockResolvedValue({
      documents: [
        {
          id: 1,
          original_filename: "ready.pdf",
          status: "processed",
          error_message: null,
          created_at: "2026-10-06T12:00:00Z",
          updated_at: "2026-10-06T12:01:00Z",
        },
      ],
      total: 1,
    });

    render(
      <App
        documentClient={client}
        chatClient={client}
      />,
    );

    expect(await screen.findByText("ready.pdf")).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByRole("textbox", {
          name: "Ask a question about your documents",
        }),
      ).toBeEnabled();
    });
  });
});
