import { resolveApiBaseUrl } from "../config/env";
import type {
  ApiErrorResponse,
  ChatRequest,
  ChatResponse,
  DocumentListResponse,
  DocumentUploadResponse,
} from "../types/api";

export const DEFAULT_REQUEST_TIMEOUT_MS = 15_000;
export const CHAT_REQUEST_TIMEOUT_MS = 75_000;
export const UPLOAD_REQUEST_TIMEOUT_MS = 120_000;

export type ApiClientErrorKind =
  | "http"
  | "network"
  | "timeout"
  | "cancelled"
  | "invalid_response"
  | "configuration";

export class ApiClientError extends Error {
  readonly kind: ApiClientErrorKind;
  readonly status: number | null;
  readonly code: string | null;

  constructor(
    message: string,
    options: {
      kind: ApiClientErrorKind;
      status?: number | null;
      code?: string | null;
      cause?: unknown;
    },
  ) {
    super(message, { cause: options.cause });
    this.name = "ApiClientError";
    this.kind = options.kind;
    this.status = options.status ?? null;
    this.code = options.code ?? null;
  }
}

export interface RequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
}

export interface ApiClient {
  listDocuments(
    limit?: number,
    options?: RequestOptions,
  ): Promise<DocumentListResponse>;
  uploadDocument(
    file: File,
    options?: RequestOptions,
  ): Promise<DocumentUploadResponse>;
  deleteDocument(
    documentId: number,
    options?: RequestOptions,
  ): Promise<void>;
  sendChat(
    request: ChatRequest,
    options?: RequestOptions,
  ): Promise<ChatResponse>;
}

type RequestState = {
  signal: AbortSignal;
  cleanup: () => void;
  didTimeout: () => boolean;
  wasCancelled: () => boolean;
};

function createRequestState(
  timeoutMs: number,
  externalSignal?: AbortSignal,
): RequestState {
  const controller = new AbortController();
  let timedOut = false;
  let cancelled = externalSignal?.aborted ?? false;

  const abortFromCaller = () => {
    cancelled = true;
    controller.abort(externalSignal?.reason);
  };

  if (externalSignal?.aborted) {
    controller.abort(externalSignal.reason);
  } else {
    externalSignal?.addEventListener("abort", abortFromCaller, {
      once: true,
    });
  }

  const timeoutId = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  return {
    signal: controller.signal,
    cleanup: () => {
      window.clearTimeout(timeoutId);
      externalSignal?.removeEventListener("abort", abortFromCaller);
    },
    didTimeout: () => timedOut,
    wasCancelled: () => cancelled,
  };
}

async function parseApiError(response: Response): Promise<ApiErrorResponse> {
  try {
    const body: unknown = await response.json();

    if (
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      const code =
        "code" in body &&
        (typeof body.code === "string" || body.code === null)
          ? body.code
          : null;

      return {
        detail: body.detail,
        code,
      };
    }
  } catch {
    // Fall through to a status-based message.
  }

  return {
    detail: `Request failed with status ${response.status}`,
    code: null,
  };
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new ApiClientError("The API returned an invalid JSON response", {
      kind: "invalid_response",
      status: response.status,
      cause: error,
    });
  }
}

export function createApiClient(
  baseUrl?: string,
): ApiClient {
  const normalizedBaseUrl = (
    baseUrl ?? resolveApiBaseUrl(import.meta.env)
  ).replace(/\/+$/, "");

  async function request<T>(
    path: string,
    init: RequestInit,
    options: RequestOptions = {},
  ): Promise<T> {
    const timeoutMs =
      options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;

    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
      throw new ApiClientError(
        "Request timeout must be greater than zero",
        { kind: "configuration" },
      );
    }

    const state = createRequestState(timeoutMs, options.signal);

    try {
      const response = await fetch(
        `${normalizedBaseUrl}${path}`,
        {
          ...init,
          signal: state.signal,
        },
      );

      if (!response.ok) {
        const errorBody = await parseApiError(response);

        throw new ApiClientError(errorBody.detail, {
          kind: "http",
          status: response.status,
          code: errorBody.code ?? null,
        });
      }

      if (response.status === 204) {
        return undefined as T;
      }

      return await parseJsonResponse<T>(response);
    } catch (error) {
      if (error instanceof ApiClientError) {
        throw error;
      }

      if (state.didTimeout()) {
        throw new ApiClientError("The request timed out", {
          kind: "timeout",
          cause: error,
        });
      }

      if (state.wasCancelled()) {
        throw new ApiClientError("The request was cancelled", {
          kind: "cancelled",
          cause: error,
        });
      }

      throw new ApiClientError("Unable to reach the API", {
        kind: "network",
        cause: error,
      });
    } finally {
      state.cleanup();
    }
  }

  return {
    async listDocuments(limit = 50, options = {}) {
      const params = new URLSearchParams({
        limit: String(limit),
      });

      return request<DocumentListResponse>(
        `/api/documents?${params.toString()}`,
        {
          method: "GET",
          headers: {
            Accept: "application/json",
          },
        },
        options,
      );
    },

    async uploadDocument(file, options = {}) {
      const body = new FormData();
      body.append("file", file);

      return request<DocumentUploadResponse>(
        "/api/documents",
        {
          method: "POST",
          headers: {
            Accept: "application/json",
          },
          body,
        },
        {
          timeoutMs: UPLOAD_REQUEST_TIMEOUT_MS,
          ...options,
        },
      );
    },

    async deleteDocument(documentId, options = {}) {
      await request<void>(
        `/api/documents/${documentId}`,
        {
          method: "DELETE",
          headers: {
            Accept: "application/json",
          },
        },
        options,
      );
    },

    async sendChat(chatRequest, options = {}) {
      return request<ChatResponse>(
        "/api/chat",
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(chatRequest),
        },
        {
          timeoutMs: CHAT_REQUEST_TIMEOUT_MS,
          ...options,
        },
      );
    },
  };
}

let defaultApiClient: ApiClient | null = null;

export function getApiClient(): ApiClient {
  if (defaultApiClient === null) {
    defaultApiClient = createApiClient();
  }

  return defaultApiClient;
}
