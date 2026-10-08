import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatComposer } from "./ChatComposer";

describe("ChatComposer accessibility", () => {
  it("exposes a label and keyboard instructions", () => {
    render(
      <ChatComposer
        value=""
        onChange={vi.fn()}
      />,
    );

    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });

    expect(input).toHaveAttribute(
      "aria-describedby",
      "chat-composer-hint",
    );
    expect(
      screen.getByText(
        "Press Enter to send. Press Shift+Enter for a new line.",
      ),
    ).toBeInTheDocument();
  });

  it("submits a trimmed question with Enter", () => {
    const onSubmit = vi.fn();

    render(
      <ChatComposer
        value="  What is the warranty?  "
        onChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.keyDown(
      screen.getByRole("textbox", {
        name: "Ask a question about your documents",
      }),
      {
        key: "Enter",
        code: "Enter",
      },
    );

    expect(onSubmit).toHaveBeenCalledWith(
      "What is the warranty?",
    );
  });

  it("keeps Shift+Enter available for multiline input", () => {
    const onSubmit = vi.fn();

    render(
      <ChatComposer
        value="First line"
        onChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.keyDown(
      screen.getByRole("textbox", {
        name: "Ask a question about your documents",
      }),
      {
        key: "Enter",
        code: "Enter",
        shiftKey: true,
      },
    );

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("keeps the textbox focusable while an answer is pending", () => {
    render(
      <ChatComposer
        value="Question"
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        busy
      />,
    );

    const input = screen.getByRole("textbox", {
      name: "Ask a question about your documents",
    });

    input.focus();

    expect(input).toHaveFocus();
    expect(input).not.toBeDisabled();
    expect(input).toHaveAttribute("readonly");
    expect(input).toHaveAttribute("aria-busy", "true");
    expect(
      screen.getByRole("button", { name: "Send question" }),
    ).toBeDisabled();
  });

  it("uses true disabled semantics when chat is unavailable", () => {
    render(
      <ChatComposer
        value=""
        onChange={vi.fn()}
        disabled
      />,
    );

    expect(
      screen.getByRole("textbox", {
        name: "Ask a question about your documents",
      }),
    ).toBeDisabled();
  });
});
