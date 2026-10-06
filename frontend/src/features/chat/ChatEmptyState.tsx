export interface ChatEmptyStateProps {
  onSuggestionSelect?: (question: string) => void;
}

const EXAMPLE_QUESTIONS = [
  "What does this document say about…?",
  "Summarize the key requirements",
];

export function ChatEmptyState({
  onSuggestionSelect,
}: ChatEmptyStateProps) {
  return (
    <div className="chat-empty">
      <div className="chat-empty-mark" aria-hidden="true">
        <span>AI</span>
      </div>

      <div className="chat-empty-copy">
        <h2>Answers you can trace back to the source</h2>
        <p>
          Upload a document, then ask a question. Answers will include
          the document and page used as evidence.
        </p>
      </div>

      <div className="suggestion-list" aria-label="Example questions">
        <span>Try asking</span>
        {EXAMPLE_QUESTIONS.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => onSuggestionSelect?.(question)}
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  );
}
