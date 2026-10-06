import { useEffect, useRef, useState } from "react";

import {
  ApiClientError,
  getApiClient,
  type ApiClient,
} from "../../services/apiClient";
import { ChatComposer } from "./ChatComposer";
import { ChatEmptyState } from "./ChatEmptyState";
import { ChatMessage } from "./ChatMessage";
import type { ChatMessageModel } from "./chatTypes";

function chatRequestError(error: unknown): string {
  if (error instanceof ApiClientError) {
    return error.message;
  }

  return "Unable to get an answer";
}

export interface ChatPanelProps {
  client?: ApiClient;
  initialMessages?: ChatMessageModel[];
}

export function ChatPanel({
  client = getApiClient(),
  initialMessages = [],
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessageModel[]>(
    initialMessages,
  );
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const requestControllerRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const messageSequenceRef = useRef(initialMessages.length);

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      requestControllerRef.current?.abort();
    };
  }, []);

  const nextMessageId = (role: "user" | "assistant") => {
    messageSequenceRef.current += 1;

    return `${role}-${messageSequenceRef.current}`;
  };

  const handleSubmit = async (question: string) => {
    if (isSending) {
      return;
    }

    const controller = new AbortController();
    requestControllerRef.current = controller;

    const userMessage: ChatMessageModel = {
      id: nextMessageId("user"),
      role: "user",
      content: question,
    };

    setRequestError(null);
    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
    ]);
    setDraft("");
    setIsSending(true);

    try {
      const response = await client.sendChat(
        { question },
        { signal: controller.signal },
      );

      if (
        !mountedRef.current ||
        requestControllerRef.current !== controller
      ) {
        return;
      }

      const assistantMessage: ChatMessageModel = {
        id: nextMessageId("assistant"),
        role: "assistant",
        content: response.answer,
        sources: response.sources,
      };

      setMessages((currentMessages) => [
        ...currentMessages,
        assistantMessage,
      ]);
    } catch (error: unknown) {
      if (
        !mountedRef.current ||
        requestControllerRef.current !== controller
      ) {
        return;
      }

      if (
        error instanceof ApiClientError &&
        error.kind === "cancelled"
      ) {
        return;
      }

      setRequestError(chatRequestError(error));
    } finally {
      if (requestControllerRef.current === controller) {
        requestControllerRef.current = null;

        if (mountedRef.current) {
          setIsSending(false);
        }
      }
    }
  };

  const handleNewChat = () => {
    requestControllerRef.current?.abort();
    requestControllerRef.current = null;
    messageSequenceRef.current = 0;
    setMessages([]);
    setDraft("");
    setRequestError(null);
    setIsSending(false);
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
          onClick={handleNewChat}
        >
          New chat
        </button>
      </header>

      <section
        className={
          messages.length === 0 && !isSending
            ? "conversation conversation-empty"
            : "conversation conversation-populated"
        }
        aria-label="Conversation"
      >
        {messages.length === 0 && !isSending ? (
          <ChatEmptyState onSuggestionSelect={setDraft} />
        ) : (
          <div className="message-list">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}

            {isSending ? (
              <div
                className="chat-message message-assistant message-pending"
                role="status"
                aria-label="Assistant is thinking"
                aria-live="polite"
              >
                <div className="message-avatar" aria-hidden="true">
                  AI
                </div>
                <div className="message-body">
                  <span className="message-author">Assistant</span>
                  <div className="thinking-indicator" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </div>
                  <span className="sr-only">Generating answer…</span>
                </div>
              </div>
            ) : null}

            {requestError ? (
              <div className="chat-request-error" role="alert">
                <strong>Could not get an answer.</strong>
                <span>{requestError}</span>
              </div>
            ) : null}
          </div>
        )}
      </section>

      <ChatComposer
        value={draft}
        onChange={setDraft}
        onSubmit={handleSubmit}
        disabled={isSending}
      />
    </main>
  );
}
