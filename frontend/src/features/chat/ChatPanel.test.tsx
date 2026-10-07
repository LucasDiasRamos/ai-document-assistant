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

function submitQuestion(question: string) {
  const input = screen.getByRole("textbox", {
    name: "Ask a question about your documents",
  });

  fireEvent.change(input, {
    target: { value: question },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Send question" }),
  );

  return input;
}

describe("ChatPanel", () => {
  it("renders a grounded answer and sources", async () => {
    const sendChat = vi.fn().mockResolvedValue({
      answer: "The warranty period is 24 months.",
      sources: [
        {
          document_id: 1,
          document: "manual.pdf",
          page: 4,
        },
      ],
    });

    render(<ChatPanel client={createClient(sendChat)} />);

    submitQuestion("What is the warranty period?");

    expect(
      screen.getByRole("article", { name: "User message" }),
    ).toHaveTextContent("What is the warranty period?");

    expect(
      await screen.findByRole("article", { name: "Assistant message" }),
    ).toHaveTextContent("The warranty period is 24 months.");
    expect(screen.getByText("manual.pdf")).toBeInTheDocument();
  });

  it("presents an unsupported question as a neutral document result", async () => {
    const sendChat = vi.fn().mockResolvedValue({
      answer:
        "I could not find that information in the uploaded documents.",
      sources: [],
    });

    render(<ChatPanel client={createClient(sendChat)} />);

    submitQuestion("Who won the World Cup?");

    const assistant = await screen.findByRole("article", {
      name: "Assistant message",
    });

    expect(assistant).toHaveClass("message-insufficient-context");
    expect(
      withinArticle(assistant, "Not found in documents"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "I could not find that information in the uploaded documents.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Sources")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("blocks empty and whitespace-only questions", () => {
    const sendChat = vi.fn();

    render(<ChatPanel client={createClient(sendChat)} />);

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

    render(<ChatPanel client={createClient(sendChat)} />);

    const input = submitQuestion("Summarize the document");

    expect(
      screen.getByRole("status", { name: "Assistant is thinking" }),
    ).toBeInTheDocument();
    expect(input).toBeDisabled();

    resolveChat?.({
      answer: "Summary complete.",
      sources: [
        {
          document_id: 1,
          document: "manual.pdf",
          page: 1,
        },
      ],
    });

    expect(
      await screen.findByRole("article", { name: "Assistant message" }),
    ).toHaveTextContent("Summary complete.");
    expect(input).toBeEnabled();
  });

  it("shows a distinct offline error with a retry path", async () => {
    const sendChat = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiClientError("Unable to reach the API", {
          kind: "network",
        }),
      )
      .mockResolvedValueOnce({
        answer: "Recovered answer.",
        sources: [
          {
            document_id: 1,
            document: "manual.pdf",
            page: 2,
          },
        ],
      });

    render(<ChatPanel client={createClient(sendChat)} />);

    submitQuestion("Can you answer this?");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Connection problem");
    expect(alert).toHaveTextContent(
      "The API could not be reached. Check your connection and try again.",
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Try again" }),
    );

    expect(await screen.findByText("Recovered answer.")).toBeInTheDocument();
    expect(sendChat).toHaveBeenCalledTimes(2);
    expect(
      screen.getAllByRole("article", { name: "User message" }),
    ).toHaveLength(1);
  });

  it("shows provider/service unavailability separately", async () => {
    const sendChat = vi.fn().mockRejectedValue(
      new ApiClientError(
        "Answer generation is temporarily unavailable",
        {
          kind: "http",
          status: 503,
        },
      ),
    );

    render(<ChatPanel client={createClient(sendChat)} />);

    submitQuestion("What does the policy say?");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "AI service temporarily unavailable",
    );
    expect(alert).toHaveTextContent(
      "Document search or answer generation is temporarily unavailable.",
    );
    expect(
      screen.getByRole("button", { name: "Try again" }),
    ).toBeEnabled();
  });

  it("shows a controlled server error for API 5xx failures", async () => {
    const sendChat = vi.fn().mockRejectedValue(
      new ApiClientError("Internal Server Error", {
        kind: "http",
        status: 500,
      }),
    );

    render(<ChatPanel client={createClient(sendChat)} />);

    submitQuestion("What changed?");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Server error");
    expect(alert).toHaveTextContent(
      "The server could not complete the request. Try again.",
    );
  });

  it("blocks chat and guides the user when no searchable documents exist", () => {
    const sendChat = vi.fn();

    render(
      <ChatPanel
        client={createClient(sendChat)}
        searchableDocumentsState="unavailable"
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: "No searchable documents yet",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Upload a PDF and wait until its status is Ready before asking questions.",
      ),
    ).toBeInTheDocument();

    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });

    expect(input).toBeDisabled();
    expect(input).toHaveAttribute(
      "placeholder",
      "Upload a ready PDF before asking a question…",
    );
    expect(sendChat).not.toHaveBeenCalled();
  });

  it("supports multiple sequential questions", async () => {
    const sendChat = vi
      .fn()
      .mockResolvedValueOnce({
        answer: "First answer.",
        sources: [
          {
            document_id: 1,
            document: "manual.pdf",
            page: 1,
          },
        ],
      })
      .mockResolvedValueOnce({
        answer: "Second answer.",
        sources: [
          {
            document_id: 1,
            document: "manual.pdf",
            page: 2,
          },
        ],
      });

    render(<ChatPanel client={createClient(sendChat)} />);

    submitQuestion("First question?");
    expect(await screen.findByText("First answer.")).toBeInTheDocument();

    submitQuestion("Second question?");
    expect(await screen.findByText("Second answer.")).toBeInTheDocument();

    expect(sendChat).toHaveBeenCalledTimes(2);
  });

  it("prevents rapid duplicate submissions while a request is active", () => {
    const sendChat = vi.fn(
      () => new Promise<ChatResponse>(() => undefined),
    );

    render(<ChatPanel client={createClient(sendChat)} />);

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
  });

  it("clears the conversation and cancels the active request on New chat", async () => {
    let requestSignal: AbortSignal | undefined;

    const sendChat = vi.fn((_request, options) => {
      requestSignal = options?.signal;

      return new Promise<ChatResponse>(() => undefined);
    });

    render(<ChatPanel client={createClient(sendChat)} />);

    submitQuestion("Pending question");

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
  });
});

function withinArticle(
  article: HTMLElement,
  text: string,
): HTMLElement {
  const match = Array.from(article.querySelectorAll("*")).find(
    (element) => element.textContent === text,
  );

  if (!(match instanceof HTMLElement)) {
    throw new Error(`Could not find "${text}" in article`);
  }

  return match;
}
