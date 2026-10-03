import { AppHeader } from "./components/AppHeader";
import { ChatPanel } from "./features/chat/ChatPanel";
import { DocumentsPanel } from "./features/documents/DocumentsPanel";

export function App() {
  return (
    <div className="app">
      <a className="skip-link" href="#main-content">
        Skip to chat
      </a>

      <AppHeader />

      <div className="workspace">
        <DocumentsPanel />
        <ChatPanel />
      </div>
    </div>
  );
}
