import type { FormEvent } from "react";

export interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: (question: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled = false,
  placeholder = "Ask a question about your documents…",
}: ChatComposerProps) {
  const trimmedQuestion = value.trim();
  const canSubmit = !disabled && trimmedQuestion.length > 0;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!canSubmit) {
      return;
    }

    onSubmit?.(trimmedQuestion);
  };

  return (
    <form
      className="composer"
      aria-label="Ask a question"
      onSubmit={handleSubmit}
    >
      <label className="sr-only" htmlFor="question">
        Ask a question about your documents
      </label>
      <textarea
        id="question"
        name="question"
        rows={1}
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
      <button
        className="send-button"
        type="submit"
        aria-label="Send question"
        disabled={!canSubmit}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="m5 12 14-7-4.5 14-3-5.5z" />
          <path d="m11.5 13.5 3-3" />
        </svg>
      </button>
    </form>
  );
}
