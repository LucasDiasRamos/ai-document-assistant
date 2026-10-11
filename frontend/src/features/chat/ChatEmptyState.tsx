export interface ChatEmptyStateProps {
  onSuggestionSelect?: (question: string) => void;
  disabled?: boolean;
}

const EXAMPLE_QUESTIONS = [
  "Summarize the key requirements.",
  "What actions does the policy describe?",
  "Which page discusses the warranty?",
];

export function ChatEmptyState({
  onSuggestionSelect,
  disabled = false,
}: ChatEmptyStateProps) {
  return (
    <div className="chat-empty">
      <div className="chat-empty-mark" aria-hidden="true">
        <span>AI</span>
      </div>

      <div className="chat-empty-copy">
        <span className="chat-empty-kicker">DOCUMENT-GROUNDED ASSISTANT</span>
        <h2>Answers you can trace back to the source</h2>
        <p>
          Choose a question or write your own. Every supported answer
          links back to its document and page.
        </p>
      </div>

      <div className="suggestion-list" aria-label="Example questions">
        <span>Get started with a question</span>
        {EXAMPLE_QUESTIONS.map((question) => (
          <button
            key={question}
            type="button"
            disabled={disabled}
            onClick={() => onSuggestionSelect?.(question)}
          >
            <span aria-hidden="true" className="suggestion-arrow">↗</span>
            {question}
          </button>
        ))}
      </div>
    </div>
  );
}
