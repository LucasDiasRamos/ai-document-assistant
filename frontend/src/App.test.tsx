import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { App } from "./App";
import type { ApiClient } from "./services/apiClient";

function createDocumentClient(): ApiClient {
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
    render(<App documentClient={createDocumentClient()} />);

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
    render(<App documentClient={createDocumentClient()} />);

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

  it("renders the document empty state and fixture chat exchange", async () => {
    render(<App documentClient={createDocumentClient()} />);

    expect(
      await screen.findByRole("heading", { name: "No documents yet" }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("article", { name: "User message" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("article", { name: "Assistant message" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Sources")).toBeInTheDocument();
  });
});
