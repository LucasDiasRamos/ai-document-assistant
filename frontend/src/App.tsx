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
