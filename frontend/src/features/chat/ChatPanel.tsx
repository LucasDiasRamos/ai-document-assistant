import { useState } from "react";

import { ChatComposer } from "./ChatComposer";
import { ChatEmptyState } from "./ChatEmptyState";
import { CHAT_FIXTURE_MESSAGES } from "./chatFixtures";
import { ChatMessage } from "./ChatMessage";
import type { ChatMessageModel } from "./chatTypes";

export interface ChatPanelProps {
  messages?: ChatMessageModel[];
  onSubmit?: (question: string) => void;
  onNewChat?: () => void;
}

export function ChatPanel({
  messages = CHAT_FIXTURE_MESSAGES,
  onSubmit,
  onNewChat,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("");

  const handleSubmit = (question: string) => {
    onSubmit?.(question);
  };

  return (
    <main className="chat-panel" id="main-content" tabIndex={-1}>
      <header className="chat-header">
        <div>
          <p className="section-kicker">Grounded Q&amp;A</p>
          <h1>Ask your documents</h1>
        </div>
        <button
          className="button button-secondary"
          type="button"
          onClick={onNewChat}
        >
          New chat
        </button>
      </header>

      <section
        className={
          messages.length === 0
            ? "conversation conversation-empty"
            : "conversation conversation-populated"
        }
        aria-label="Conversation"
      >
        {messages.length === 0 ? (
          <ChatEmptyState onSuggestionSelect={setDraft} />
        ) : (
          <div className="message-list">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
          </div>
        )}
      </section>

      <ChatComposer
        value={draft}
        onChange={setDraft}
        onSubmit={handleSubmit}
      />
    </main>
  );
}
