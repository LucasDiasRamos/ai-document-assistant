import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CitationList } from "./CitationList";

describe("CitationList", () => {
  it("renders one citation", () => {
    render(
      <CitationList
        sources={[
          {
            document_id: 1,
            document: "manual.pdf",
            page: 4,
          },
        ]}
      />,
    );

    expect(screen.getByLabelText("Sources")).toHaveAttribute(
      "data-source-count",
      "1",
    );
    expect(screen.getByText("1 source")).toBeInTheDocument();
    expect(
      screen.getByRole("listitem", {
        name: "manual.pdf, page 4",
      }),
    ).toBeInTheDocument();
  });

  it("renders multiple citations in source order", () => {
    render(
      <CitationList
        sources={[
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
        ]}
      />,
    );

    const list = screen.getByRole("list");

    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("2 sources")).toBeInTheDocument();
  });

  it("deduplicates repeated document and page pairs", () => {
    render(
      <CitationList
        sources={[
          {
            document_id: 1,
            document: "manual.pdf",
            page: 4,
          },
          {
            document_id: 1,
            document: "manual.pdf",
            page: 4,
          },
          {
            document_id: 1,
            document: "manual.pdf",
            page: 5,
          },
        ]}
      />,
    );

    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(
      screen.getAllByRole("listitem", {
        name: "manual.pdf, page 4",
      }),
    ).toHaveLength(1);
  });

  it("preserves the full filename for long citation labels", () => {
    const longFilename =
      "a-very-long-enterprise-policy-document-name-that-needs-truncation.pdf";

    render(
      <CitationList
        sources={[
          {
            document_id: 3,
            document: longFilename,
            page: 12,
          },
        ]}
      />,
    );

    expect(screen.getByTitle(longFilename)).toHaveTextContent(
      longFilename,
    );
    expect(
      screen.getByRole("listitem", {
        name: `${longFilename}, page 12`,
      }),
    ).toBeInTheDocument();
  });

  it("renders no source region when citations are absent", () => {
    render(<CitationList sources={[]} />);

    expect(screen.queryByLabelText("Sources")).not.toBeInTheDocument();
  });
});
