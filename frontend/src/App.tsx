import { useState } from "react";

import { AppHeader } from "./components/AppHeader";
import { ChatPanel } from "./features/chat/ChatPanel";
import type { SearchableDocumentsState } from "./types/app";
import { DocumentsPanel } from "./features/documents/DocumentsPanel";
import type { ApiClient } from "./services/apiClient";

export interface AppProps {
  documentClient?: ApiClient;
  chatClient?: ApiClient;
}

export function App({
  documentClient,
  chatClient,
}: AppProps) {
  const [
    searchableDocumentsState,
    setSearchableDocumentsState,
  ] = useState<SearchableDocumentsState>("unknown");

  return (
    <div className="app">
      <a className="skip-link" href="#main-content">
        Skip to chat
      </a>

      <AppHeader />

      <section className="intro-banner" aria-label="How it works">
        <div className="intro-copy">
          <p className="intro-eyebrow">YOUR DOCUMENTS, MADE SEARCHABLE</p>
          <h2>Ask questions. See the evidence.</h2>
          <p>
            Find answers in your PDFs and check the exact document
            and page behind each response.
          </p>
        </div>
        <ol className="intro-steps">
          <li><span>01</span> Upload a PDF</li>
          <li><span>02</span> Ask anything</li>
          <li><span>03</span> Check the source</li>
        </ol>
      </section>

      <div className="workspace">
        <DocumentsPanel
          client={documentClient}
          onSearchableStateChange={setSearchableDocumentsState}
        />
        <ChatPanel
          client={chatClient}
          searchableDocumentsState={searchableDocumentsState}
        />
      </div>
    </div>
  );
}
