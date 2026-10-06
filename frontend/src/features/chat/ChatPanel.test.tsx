import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ChatMessageModel } from "./chatTypes";
import { ChatPanel } from "./ChatPanel";

describe("ChatPanel", () => {
  it("renders user and assistant messages", () => {
    const messages: ChatMessageModel[] = [
      {
        id: "user-1",
        role: "user",
        content: "What is the retention period?",
      },
      {
        id: "assistant-1",
        role: "assistant",
        content: "The retention period is described in the policy.",
      },
    ];

    render(<ChatPanel messages={messages} />);

    expect(
      screen.getByRole("article", { name: "User message" }),
    ).toHaveTextContent("What is the retention period?");
    expect(
      screen.getByRole("article", { name: "Assistant message" }),
    ).toHaveTextContent(
      "The retention period is described in the policy.",
    );
  });

  it("renders long assistant answers without truncating the content", () => {
    const longAnswer =
      "This is a deliberately long answer that contains enough text to " +
      "exercise the wrapping behavior of the message body across narrow " +
      "layouts while preserving the complete grounded response for the user.";

    render(
      <ChatPanel
        messages={[
          {
            id: "assistant-long",
            role: "assistant",
            content: longAnswer,
          },
        ]}
      />,
    );

    expect(screen.getByText(longAnswer)).toBeInTheDocument();
    expect(screen.getByText(longAnswer)).toHaveClass("message-content");
  });

  it("renders multiple citations for an assistant answer", () => {
    render(
      <ChatPanel
        messages={[
          {
            id: "assistant-sources",
            role: "assistant",
            content: "The answer is supported by two pages.",
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
          },
        ]}
      />,
    );

    expect(screen.getByLabelText("Sources")).toBeInTheDocument();
    expect(screen.getByText("manual.pdf")).toBeInTheDocument();
    expect(screen.getByText("Page 4")).toBeInTheDocument();
    expect(screen.getByText("policy.pdf")).toBeInTheDocument();
    expect(screen.getByText("Page 9")).toBeInTheDocument();
  });

  it("renders the empty conversation state", () => {
    render(<ChatPanel messages={[]} />);

    expect(
      screen.getByRole("heading", {
        name: "Answers you can trace back to the source",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Example questions"),
    ).toBeInTheDocument();
  });

  it("copies an example question into the composer", () => {
    render(<ChatPanel messages={[]} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: "Summarize the key requirements",
      }),
    );

    expect(
      screen.getByRole("textbox", {
        name: "Ask a question about your documents",
      }),
    ).toHaveValue("Summarize the key requirements");
  });

  it("exposes the prepared submit callback without adding local messages", () => {
    const onSubmit = vi.fn();

    render(<ChatPanel messages={[]} onSubmit={onSubmit} />);

    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });

    fireEvent.change(input, {
      target: { value: "  What is the warranty?  " },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );

    expect(onSubmit).toHaveBeenCalledWith("What is the warranty?");
    expect(
      screen.queryByRole("article", { name: "User message" }),
    ).not.toBeInTheDocument();
  });

  it("keeps send disabled for an empty composer", () => {
    render(<ChatPanel messages={[]} />);

    expect(
      screen.getByRole("button", { name: "Send question" }),
    ).toBeDisabled();
  });
});
