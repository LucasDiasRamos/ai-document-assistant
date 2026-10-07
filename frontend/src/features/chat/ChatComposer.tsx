import type {
  FormEvent,
  KeyboardEvent,
} from "react";

export interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: (question: string) => void;
  disabled?: boolean;
  busy?: boolean;
  placeholder?: string;
}

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled = false,
  busy = false,
  placeholder = "Ask a question about your documents…",
}: ChatComposerProps) {
  const trimmedQuestion = value.trim();
  const canSubmit =
    !disabled && !busy && trimmedQuestion.length > 0;

  const submitCurrentQuestion = () => {
    if (!canSubmit) {
      return;
    }

    onSubmit?.(trimmedQuestion);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitCurrentQuestion();
  };

  const handleKeyDown = (
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (
      event.key !== "Enter" ||
      event.shiftKey ||
      event.nativeEvent.isComposing
    ) {
      return;
    }

    event.preventDefault();
    submitCurrentQuestion();
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
      <span className="sr-only" id="chat-composer-hint">
        Press Enter to send. Press Shift+Enter for a new line.
      </span>
      <textarea
        id="question"
        name="question"
        rows={1}
        value={value}
        disabled={disabled}
        readOnly={busy}
        aria-busy={busy}
        aria-describedby="chat-composer-hint"
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <button
        className="send-button"
        type="submit"
        aria-label="Send question"
        aria-busy={busy}
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
