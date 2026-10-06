import { render, screen } from "@testing-library/react";
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
      screen.getByRole("button", { name: "Send question" }),
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

  it("renders coherent empty states before user interaction", async () => {
    const client = createApiClient();

    render(
      <App
        documentClient={client}
        chatClient={client}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "No documents yet" }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", {
        name: "Answers you can trace back to the source",
      }),
    ).toBeInTheDocument();
  });
});
