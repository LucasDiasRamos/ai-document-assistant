export function AppHeader() {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          AI
        </span>
        <div>
          <p className="brand-kicker">Document intelligence</p>
          <p className="brand-name">AI Document Assistant</p>
        </div>
      </div>

      <span className="status-badge">
        <span className="status-dot" aria-hidden="true" />
        Local workspace
      </span>
    </header>
  );
}
