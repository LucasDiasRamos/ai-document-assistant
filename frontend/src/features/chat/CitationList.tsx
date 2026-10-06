import type { ChatSource } from "../../types/api";

export interface CitationListProps {
  sources: ChatSource[];
}

export function CitationList({ sources }: CitationListProps) {
  if (sources.length === 0) {
    return null;
  }

  return (
    <div className="citation-block" aria-label="Sources">
      <span className="citation-label">Sources</span>
      <ul className="citation-list">
        {sources.map((source, index) => (
          <li
            className="citation-item"
            key={`${source.document_id}-${source.page}-${index}`}
          >
            <span className="citation-document">
              {source.document}
            </span>
            <span className="citation-page">Page {source.page}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
