export function ChatPanel() {
  return (
    <main className="chat-panel" id="main-content" tabIndex={-1}>
      <header className="chat-header">
        <div>
          <p className="section-kicker">Grounded Q&amp;A</p>
          <h1>Ask your documents</h1>
        </div>
        <button className="button button-secondary" type="button">
          New chat
        </button>
      </header>

      <section className="conversation" aria-label="Conversation">
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
            <button type="button">What does this document say about…?</button>
            <button type="button">Summarize the key requirements</button>
          </div>
        </div>
      </section>

      <form
        className="composer"
        aria-label="Ask a question"
        onSubmit={(event) => event.preventDefault()}
      >
        <label className="sr-only" htmlFor="question">
          Ask a question about your documents
        </label>
        <textarea
          id="question"
          name="question"
          rows={1}
          placeholder="Ask a question about your documents…"
        />
        <button
          className="send-button"
          type="submit"
          aria-label="Send question"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m5 12 14-7-4.5 14-3-5.5z" />
            <path d="m11.5 13.5 3-3" />
          </svg>
        </button>
      </form>
    </main>
  );
}
