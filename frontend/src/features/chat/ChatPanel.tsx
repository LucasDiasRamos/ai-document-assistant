import { useEffect, useRef, useState } from "react";

import {
  ApiClientError,
  getApiClient,
  type ApiClient,
} from "../../services/apiClient";
import { ChatComposer } from "./ChatComposer";
import { ChatEmptyState } from "./ChatEmptyState";
import { ChatMessage } from "./ChatMessage";
import type { SearchableDocumentsState } from "../../types/app";
import type { ChatMessageModel } from "./chatTypes";

type ChatRequestFailureKind =
  | "network"
  | "service"
  | "server"
  | "request";

interface ChatRequestFailure {
  kind: ChatRequestFailureKind;
  title: string;
  message: string;
  question: string;
  retryable: boolean;
}

function classifyChatFailure(
  error: unknown,
  question: string,
): ChatRequestFailure {
  if (error instanceof ApiClientError) {
    if (error.kind === "network") {
      return {
        kind: "network",
        title: "Connection problem",
        message:
          "The API could not be reached. Check your connection and try again.",
        question,
        retryable: true,
      };
    }

    if (error.status === 429) {
      return {
        kind: "service",
        title: "Usage limit reached",
        message: "Too many requests. Wait a moment before asking again.",
        question,
        retryable: false,
      };
    }

    if (error.status === 503) {
      return {
        kind: "service",
        title: "AI service temporarily unavailable",
        message:
          "Document search or answer generation is temporarily unavailable. Try again in a moment.",
        question,
        retryable: true,
      };
    }

    if (error.status !== null && error.status >= 500) {
      return {
        kind: "server",
        title: "Server error",
        message:
          "The server could not complete the request. Try again.",
        question,
        retryable: true,
      };
    }

    return {
      kind: "request",
      title: "Could not get an answer",
      message: error.message,
      question,
      retryable: false,
    };
  }

  return {
    kind: "server",
    title: "Something went wrong",
    message: "The request could not be completed. Try again.",
    question,
    retryable: true,
  };
}

export interface ChatPanelProps {
  client?: ApiClient;
  initialMessages?: ChatMessageModel[];
  searchableDocumentsState?: SearchableDocumentsState;
}

export function ChatPanel({
  client = getApiClient(),
  initialMessages = [],
  searchableDocumentsState = "available",
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessageModel[]>(
    initialMessages,
  );
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [requestFailure, setRequestFailure] =
    useState<ChatRequestFailure | null>(null);
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

  useEffect(() => {
    if (
      searchableDocumentsState === "unavailable" &&
      requestControllerRef.current !== null
    ) {
      requestControllerRef.current.abort();
      requestControllerRef.current = null;
      setIsSending(false);
    }
  }, [searchableDocumentsState]);

  const nextMessageId = (role: "user" | "assistant") => {
    messageSequenceRef.current += 1;

    return `${role}-${messageSequenceRef.current}`;
  };

  const submitQuestion = async (
    question: string,
    appendUserMessage: boolean,
  ) => {
    if (
      (searchableDocumentsState === "unavailable" ||
        searchableDocumentsState === "unknown") ||
      isSending ||
      requestControllerRef.current !== null
    ) {
      return;
    }

    const controller = new AbortController();
    requestControllerRef.current = controller;

    if (appendUserMessage) {
      const userMessage: ChatMessageModel = {
        id: nextMessageId("user"),
        role: "user",
        content: question,
      };

      setMessages((currentMessages) => [
        ...currentMessages,
        userMessage,
      ]);
      setDraft("");
    }

    setRequestFailure(null);
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
        variant:
          response.sources.length === 0
            ? "insufficient-context"
            : "standard",
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

      setRequestFailure(classifyChatFailure(error, question));
    } finally {
      if (requestControllerRef.current === controller) {
        requestControllerRef.current = null;

        if (mountedRef.current) {
          setIsSending(false);
        }
      }
    }
  };

  const handleSubmit = (question: string) => {
    void submitQuestion(question, true);
  };

  const handleRetry = () => {
    if (!requestFailure?.retryable) {
      return;
    }

    void submitQuestion(requestFailure.question, false);
  };

  const handleNewChat = () => {
    requestControllerRef.current?.abort();
    requestControllerRef.current = null;
    messageSequenceRef.current = 0;
    setMessages([]);
    setDraft("");
    setRequestFailure(null);
    setIsSending(false);
  };

  const documentsUnavailable =
    searchableDocumentsState === "unavailable";
  const documentsUnknown =
    searchableDocumentsState === "unknown";
  const composerDisabled =
    documentsUnavailable || documentsUnknown;

  const composerPlaceholder = documentsUnavailable
    ? "Upload a ready PDF before asking a question…"
    : documentsUnknown
      ? "Checking document availability…"
      : "Ask a question about your documents…";

  const showEmptyState =
    messages.length === 0 && !isSending && !documentsUnavailable;
  const showNoDocumentsState =
    messages.length === 0 && !isSending && documentsUnavailable;

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
          showEmptyState || showNoDocumentsState
            ? "conversation conversation-empty"
            : "conversation conversation-populated"
        }
        aria-label="Conversation"
        aria-busy={isSending}
      >
        {showNoDocumentsState ? (
          <div
            className="chat-readiness-state"
            role="status"
            aria-live="polite"
          >
            <div className="chat-empty-mark" aria-hidden="true">
              <span>PDF</span>
            </div>
            <div>
              <h2>No searchable documents yet</h2>
              <p>
                Upload a PDF and wait until its status is Ready before
                asking questions.
              </p>
            </div>
          </div>
        ) : showEmptyState ? (
          <ChatEmptyState
            onSuggestionSelect={setDraft}
            disabled={composerDisabled}
          />
        ) : (
          <div
            className="message-list"
            role="log"
            aria-label="Conversation messages"
            aria-live="polite"
            aria-relevant="additions text"
          >
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

            {documentsUnavailable ? (
              <div
                className="chat-readiness-inline"
                role="status"
                aria-live="polite"
              >
                <strong>No searchable documents available.</strong>
                <span>
                  Upload or finish processing a PDF before asking
                  another question.
                </span>
              </div>
            ) : null}

            {requestFailure ? (
              <div
                className={`chat-request-error error-${requestFailure.kind}`}
                role="alert"
              >
                <div>
                  <strong>{requestFailure.title}</strong>
                  <span>{requestFailure.message}</span>
                </div>
                {requestFailure.retryable ? (
                  <button
                    className="button button-secondary chat-retry-button"
                    type="button"
                    disabled={composerDisabled}
                    onClick={handleRetry}
                  >
                    Try again
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        )}
      </section>

      <ChatComposer
        value={draft}
        onChange={setDraft}
        onSubmit={handleSubmit}
        disabled={composerDisabled}
        busy={isSending}
        placeholder={composerPlaceholder}
      />
    </main>
  );
}
