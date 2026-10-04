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
