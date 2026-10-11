export type DocumentStatus =
  | "uploaded"
  | "processing"
  | "processed"
  | "failed";

export interface DocumentSummary {
  id: number;
  original_filename: string;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export type DocumentDetail = DocumentSummary;
export type DocumentUploadResponse = DocumentSummary;

export interface DocumentListResponse {
  documents: DocumentSummary[];
  total: number;
}

export interface ApiErrorResponse {
  detail: string;
  code?: string | null;
}

export interface ApiValidationIssue {
  type: string | null;
  location: Array<string | number>;
  message: string;
}

export interface ChatRequest {
  question: string;
}

export interface ChatSource {
  document_id: number;
  document: string;
  page: number;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
}

export interface ConversationCreated {
  token: string;
  expires_at: string;
}

export interface StoredConversationMessage {
  role: "user" | "assistant";
  content: string;
  sources: ChatSource[];
}

export interface ConversationHistory {
  expires_at: string;
  messages: StoredConversationMessage[];
}
