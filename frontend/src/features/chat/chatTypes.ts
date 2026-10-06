import type { ChatSource } from "../../types/api";

export type ChatMessageRole = "user" | "assistant";

export interface ChatMessageModel {
  id: string;
  role: ChatMessageRole;
  content: string;
  sources?: ChatSource[];
}
