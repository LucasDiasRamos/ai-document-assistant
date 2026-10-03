export function DocumentsPanel() {
  return (
    <aside className="documents-panel" aria-labelledby="documents-title">
      <div className="panel-heading">
        <div>
          <p className="section-kicker">Knowledge base</p>
          <h2 id="documents-title">Documents</h2>
        </div>
        <span className="document-count" aria-label="No documents uploaded">
          0
        </span>
      </div>

      <div className="documents-empty">
        <div className="empty-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" role="presentation">
            <path d="M7 3.75h6.6L18.25 8.4V20.25H7z" />
            <path d="M13.5 3.75V8.5h4.75M9.5 12h6M9.5 15h6" />
          </svg>
        </div>
        <div>
          <h3>No documents yet</h3>
          <p>
            Add a PDF to create a searchable knowledge base for grounded
            answers.
          </p>
        </div>
      </div>

      <button className="button button-primary upload-button" type="button">
        <span aria-hidden="true">+</span>
        Upload PDF
      </button>

      <p className="panel-footnote">
        PDF files only. Upload wiring arrives in the document workflow.
      </p>
    </aside>
  );
}
