import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../services/apiClient";
import { DocumentsPanel } from "./DocumentsPanel";

function createClient(): ApiClient {
  return {
    listDocuments: vi.fn().mockResolvedValue({
      documents: [
        {
          id: 1,
          original_filename: "manual.pdf",
          status: "processed",
          error_message: null,
          created_at: "2026-10-07T12:00:00Z",
          updated_at: "2026-10-07T12:01:00Z",
        },
      ],
      total: 1,
    }),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    sendChat: vi.fn(),
  };
}

describe("DocumentsPanel accessibility", () => {
  it("moves focus into delete confirmation and restores it on cancel", async () => {
    render(<DocumentsPanel client={createClient()} />);

    const trigger = await screen.findByRole("button", {
      name: "Delete manual.pdf",
    });

    trigger.focus();
    fireEvent.click(trigger);

    const confirm = screen.getByRole("button", {
      name: "Delete",
    });

    await waitFor(() => {
      expect(confirm).toHaveFocus();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Cancel" }),
    );

    await waitFor(() => {
      expect(trigger).toHaveFocus();
    });
  });

  it("keeps upload and delete controls discoverable by accessible name", async () => {
    render(<DocumentsPanel client={createClient()} />);

    await screen.findByText("manual.pdf");

    expect(
      screen.getByRole("button", { name: "Upload PDF" }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Choose PDF to upload"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete manual.pdf" }),
    ).toBeInTheDocument();
  });
});
