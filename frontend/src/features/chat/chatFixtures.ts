import type { ChatMessageModel } from "./chatTypes";

export const CHAT_FIXTURE_MESSAGES: ChatMessageModel[] = [
  {
    id: "fixture-user-1",
    role: "user",
    content: "What are the main requirements described in the uploaded document?",
  },
  {
    id: "fixture-assistant-1",
    role: "assistant",
    content:
      "The document highlights three main requirements: keep the implementation traceable, preserve source metadata throughout the workflow, and make user-facing results verifiable against the original material. It also recommends keeping the initial architecture small enough to inspect and evolve without hiding the retrieval pipeline behind unnecessary abstractions.",
    sources: [
      {
        document_id: 1,
        document: "project-requirements.pdf",
        page: 3,
      },
      {
        document_id: 1,
        document: "project-requirements.pdf",
        page: 7,
      },
    ],
  },
];
