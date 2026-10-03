import { render, screen } from "@testing-library/react";

import { App } from "./App";

describe("App", () => {
  it("renders the document and chat workspace", () => {
    render(<App />);

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
  });

  it("exposes a keyboard skip link to the chat region", () => {
    render(<App />);

    expect(
      screen.getByRole("link", { name: "Skip to chat" }),
    ).toHaveAttribute("href", "#main-content");

    expect(screen.getByRole("main")).toHaveAttribute(
      "id",
      "main-content",
    );
  });

  it("renders coherent empty states before data wiring", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "No documents yet" }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", {
        name: "Answers you can trace back to the source",
      }),
    ).toBeInTheDocument();
  });
});
