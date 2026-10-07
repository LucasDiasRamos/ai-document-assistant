import type { ChatSource } from "../../types/api";

export type ChatMessageRole = "user" | "assistant";
export type ChatMessageVariant = "standard" | "insufficient-context";
export interface ChatMessageModel {
  id: string;
  role: ChatMessageRole;
  content: string;
  sources?: ChatSource[];
  variant?: ChatMessageVariant;
}
