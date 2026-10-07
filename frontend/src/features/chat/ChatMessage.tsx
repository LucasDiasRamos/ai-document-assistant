import { CitationList } from "./CitationList";
import type { ChatMessageModel } from "./chatTypes";

export interface ChatMessageProps {
  message: ChatMessageModel;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isAssistant = message.role === "assistant";

  return (
    <article
      className={[
        "chat-message",
        `message-${message.role}`,
        message.variant === "insufficient-context"
          ? "message-insufficient-context"
          : "",
      ]
        .filter(Boolean)
        .join(" ")}
      aria-label={isAssistant ? "Assistant message" : "User message"}
    >
      <div className="message-avatar" aria-hidden="true">
        {isAssistant ? "AI" : "You"}
      </div>

      <div className="message-body">
        <span className="message-author">
          {isAssistant ? "Assistant" : "You"}
        </span>
        {isAssistant &&
        message.variant === "insufficient-context" ? (
          <span className="message-state-label">
            Not found in documents
          </span>
        ) : null}

        <p className="message-content">{message.content}</p>

        {isAssistant && message.sources ? (
          <CitationList sources={message.sources} />
        ) : null}
      </div>
    </article>
  );
}
