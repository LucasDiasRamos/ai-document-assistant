import { render, screen } from "@testing-library/react";

import { App } from "./App";

describe("App", () => {
  it("renders the application shell", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "AI Document Assistant" }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(/upload documents, ask questions/i),
    ).toBeInTheDocument();
  });
});
