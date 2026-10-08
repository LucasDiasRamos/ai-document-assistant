import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../services/apiClient";
import { ChatPanel } from "./ChatPanel";

function createClient(): ApiClient {
  return {
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    sendChat: vi.fn(),
  };
}

describe("ChatPanel accessibility", () => {
  it("exposes the conversation as an accessible live log", () => {
    render(
      <ChatPanel
        client={createClient()}
        initialMessages={[
          {
            id: "user-1",
            role: "user",
            content: "Existing question",
          },
          {
            id: "assistant-1",
            role: "assistant",
            content: "Existing answer",
            sources: [],
          },
        ]}
      />,
    );

    const conversation = screen.getByRole("region", {
      name: "Conversation",
    });
    const log = screen.getByRole("log", {
      name: "Conversation messages",
    });

    expect(conversation).toHaveAttribute("aria-busy", "false");
    expect(log).toHaveAttribute("aria-live", "polite");
    expect(log).toHaveAttribute(
      "aria-relevant",
      "additions text",
    );
  });

  it("announces the no-searchable-documents state", () => {
    render(
      <ChatPanel
        client={createClient()}
        searchableDocumentsState="unavailable"
      />,
    );

    expect(
      screen.getByRole("status"),
    ).toHaveTextContent("No searchable documents yet");
    expect(
      screen.getByRole("textbox", {
        name: "Ask a question about your documents",
      }),
    ).toBeDisabled();
  });
});
