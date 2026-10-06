import type { ChatSource } from "../../types/api";

export interface CitationListProps {
  sources: ChatSource[];
}

function uniqueSources(sources: ChatSource[]): ChatSource[] {
  const seen = new Set<string>();

  return sources.filter((source) => {
    const key = `${source.document_id}:${source.page}`;

    if (seen.has(key)) {
      return false;
    }

    seen.add(key);
    return true;
  });
}

export function CitationList({ sources }: CitationListProps) {
  const citations = uniqueSources(sources);

  if (citations.length === 0) {
    return null;
  }

  const sourceLabel =
    citations.length === 1 ? "1 source" : `${citations.length} sources`;

  return (
    <div
      className="citation-block"
      aria-label="Sources"
      data-source-count={citations.length}
    >
      <div className="citation-heading">
        <span className="citation-label">Sources</span>
        <span className="citation-count">{sourceLabel}</span>
      </div>

      <ul className="citation-list">
        {citations.map((source) => (
          <li
            className="citation-item"
            key={`${source.document_id}-${source.page}`}
            aria-label={`${source.document}, page ${source.page}`}
          >
            <span
              className="citation-document"
              title={source.document}
            >
              {source.document}
            </span>
            <span className="citation-page">Page {source.page}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
