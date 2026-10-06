import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  ApiClientError,
  type ApiClient,
} from "../../services/apiClient";
import type { ChatResponse } from "../../types/api";
import { ChatPanel } from "./ChatPanel";

function createClient(
  sendChat: ApiClient["sendChat"] = vi.fn(),
): ApiClient {
  return {
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    sendChat,
  };
}

describe("ChatPanel", () => {
  it("submits a question and renders the grounded answer and sources", async () => {
    const sendChat = vi.fn().mockResolvedValue({
      answer: "The warranty period is 24 months.",
      sources: [
        {
          document_id: 1,
          document: "manual.pdf",
          page: 4,
        },
        {
          document_id: 2,
          document: "policy.pdf",
          page: 9,
        },
      ],
    });
    const client = createClient(sendChat);

    render(<ChatPanel client={client} />);

    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });

    fireEvent.change(input, {
      target: { value: "What is the warranty period?" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );

    expect(
      screen.getByRole("article", { name: "User message" }),
    ).toHaveTextContent("What is the warranty period?");

    expect(sendChat).toHaveBeenCalledWith(
      { question: "What is the warranty period?" },
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );

    expect(
      await screen.findByRole("article", { name: "Assistant message" }),
    ).toHaveTextContent("The warranty period is 24 months.");

    expect(screen.getByText("manual.pdf")).toBeInTheDocument();
    expect(screen.getByText("Page 4")).toBeInTheDocument();
    expect(screen.getByText("policy.pdf")).toBeInTheDocument();
    expect(screen.getByText("Page 9")).toBeInTheDocument();

    expect(input).toBeEnabled();
    expect(input).toHaveValue("");
  });

  it("blocks empty and whitespace-only questions", () => {
    const sendChat = vi.fn();
    const client = createClient(sendChat);

    render(<ChatPanel client={client} />);

    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });
    const sendButton = screen.getByRole("button", {
      name: "Send question",
    });

    expect(sendButton).toBeDisabled();

    fireEvent.change(input, {
      target: { value: "   " },
    });

    expect(sendButton).toBeDisabled();
    expect(sendChat).not.toHaveBeenCalled();
  });

  it("shows a pending assistant state while waiting for the API", async () => {
    let resolveChat:
      | ((response: ChatResponse) => void)
      | undefined;

    const sendChat = vi.fn(
      () =>
        new Promise<ChatResponse>((resolve) => {
          resolveChat = resolve;
        }),
    );
    const client = createClient(sendChat);

    render(<ChatPanel client={client} />);

    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });

    fireEvent.change(input, {
      target: { value: "Summarize the document" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );

    expect(
      screen.getByRole("status", { name: "Assistant is thinking" }),
    ).toBeInTheDocument();
    expect(input).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Send question" }),
    ).toBeDisabled();

    resolveChat?.({
      answer: "Summary complete.",
      sources: [],
    });

    expect(
      await screen.findByRole("article", { name: "Assistant message" }),
    ).toHaveTextContent("Summary complete.");

    expect(
      screen.queryByRole("status", { name: "Assistant is thinking" }),
    ).not.toBeInTheDocument();
    expect(input).toBeEnabled();
  });

  it("retains the user question and restores the composer after API failure", async () => {
    const sendChat = vi.fn().mockRejectedValue(
      new ApiClientError("Unable to reach the API", {
        kind: "network",
      }),
    );
    const client = createClient(sendChat);

    render(<ChatPanel client={client} />);

    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });

    fireEvent.change(input, {
      target: { value: "What changed?" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to reach the API",
    );
    expect(
      screen.getByRole("article", { name: "User message" }),
    ).toHaveTextContent("What changed?");
    expect(
      screen.queryByRole("article", { name: "Assistant message" }),
    ).not.toBeInTheDocument();
    expect(input).toBeEnabled();
  });

  it("supports multiple sequential questions", async () => {
    const sendChat = vi
      .fn()
      .mockResolvedValueOnce({
        answer: "First answer.",
        sources: [],
      })
      .mockResolvedValueOnce({
        answer: "Second answer.",
        sources: [],
      });
    const client = createClient(sendChat);

    render(<ChatPanel client={client} />);

    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });

    fireEvent.change(input, {
      target: { value: "First question?" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );

    expect(await screen.findByText("First answer.")).toBeInTheDocument();

    fireEvent.change(input, {
      target: { value: "Second question?" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );

    expect(await screen.findByText("Second answer.")).toBeInTheDocument();

    expect(sendChat).toHaveBeenCalledTimes(2);
    expect(
      screen.getAllByRole("article", { name: "User message" }),
    ).toHaveLength(2);
    expect(
      screen.getAllByRole("article", { name: "Assistant message" }),
    ).toHaveLength(2);
  });

  it("prevents rapid duplicate submissions while a request is active", async () => {
    const sendChat = vi.fn(
      () => new Promise<ChatResponse>(() => undefined),
    );
    const client = createClient(sendChat);

    render(<ChatPanel client={client} />);

    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });
    const sendButton = screen.getByRole("button", {
      name: "Send question",
    });

    fireEvent.change(input, {
      target: { value: "Only send this once" },
    });

    fireEvent.click(sendButton);
    fireEvent.click(sendButton);
    fireEvent.submit(sendButton.closest("form")!);

    expect(sendChat).toHaveBeenCalledTimes(1);
    expect(
      screen.getAllByRole("article", { name: "User message" }),
    ).toHaveLength(1);
  });

  it("clears the conversation and cancels the active request on New chat", async () => {
    let requestSignal: AbortSignal | undefined;

    const sendChat = vi.fn((_request, options) => {
      requestSignal = options?.signal;

      return new Promise<ChatResponse>(() => undefined);
    });
    const client = createClient(sendChat);

    render(<ChatPanel client={client} />);

    fireEvent.change(
      screen.getByRole("textbox", {
        name: "Ask a question about your documents",
      }),
      {
        target: { value: "Pending question" },
      },
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );

    await waitFor(() => {
      expect(requestSignal).toBeDefined();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "New chat" }),
    );

    expect(requestSignal?.aborted).toBe(true);
    expect(
      screen.queryByRole("article", { name: "User message" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Answers you can trace back to the source",
      }),
    ).toBeInTheDocument();
  });

  it("renders supplied initial messages for presentation reuse", () => {
    render(
      <ChatPanel
        client={createClient()}
        initialMessages={[
          {
            id: "user-existing",
            role: "user",
            content: "Existing question",
          },
          {
            id: "assistant-existing",
            role: "assistant",
            content: "Existing grounded answer",
            sources: [
              {
                document_id: 3,
                document: "existing.pdf",
                page: 7,
              },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByText("Existing question")).toBeInTheDocument();
    expect(screen.getByText("Existing grounded answer")).toBeInTheDocument();
    expect(screen.getByText("existing.pdf")).toBeInTheDocument();
  });
});
