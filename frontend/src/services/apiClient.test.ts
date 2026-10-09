import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiClientError,
  createApiClient,
} from "./apiClient";

function jsonResponse(
  body: unknown,
  init: ResponseInit = {},
): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("ApiClient", () => {
  it("lists documents and preserves the backend response shape", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        documents: [
          {
            id: 7,
            original_filename: "manual.pdf",
            status: "processed",
            error_message: null,
            created_at: "2026-10-03T12:00:00Z",
            updated_at: "2026-10-03T12:01:00Z",
          },
        ],
        total: 1,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = createApiClient("http://localhost:8000/api/");
    const result = await client.listDocuments(25);

    expect(result.total).toBe(1);
    expect(result.documents[0]?.original_filename).toBe("manual.pdf");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/documents?limit=25",
      expect.objectContaining({
        method: "GET",
      }),
    );
  });


  it("uses the same-origin API root without duplicating the prefix", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        documents: [],
        total: 0,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = createApiClient("/api");

    await client.listDocuments();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/documents?limit=50",
      expect.objectContaining({
        method: "GET",
      }),
    );
  });

  it("preserves FastAPI validation issue details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            detail: [
              {
                type: "string_too_short",
                loc: ["body", "question"],
                msg: "String should have at least 1 character",
                input: "",
              },
              {
                type: "less_than_equal",
                loc: ["query", "limit"],
                msg: "Input should be less than or equal to 100",
                input: 101,
              },
            ],
          },
          { status: 422 },
        ),
      ),
    );

    const client = createApiClient("/api");

    await expect(
      client.sendChat({ question: "" }),
    ).rejects.toMatchObject({
      name: "ApiClientError",
      kind: "http",
      status: 422,
      message:
        "question: String should have at least 1 character; " +
        "limit: Input should be less than or equal to 100",
      validationIssues: [
        {
          type: "string_too_short",
          location: ["body", "question"],
          message: "String should have at least 1 character",
        },
        {
          type: "less_than_equal",
          location: ["query", "limit"],
          message: "Input should be less than or equal to 100",
        },
      ],
    });
  });

  it("maps structured API errors to ApiClientError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            detail: "Document not found",
            code: "document_not_found",
          },
          { status: 404 },
        ),
      ),
    );

    const client = createApiClient("http://localhost:8000/api");

    await expect(
      client.deleteDocument(999),
    ).rejects.toMatchObject({
      name: "ApiClientError",
      message: "Document not found",
      kind: "http",
      status: 404,
      code: "document_not_found",
    });
  });

  it("maps network failures to a predictable client error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("fetch failed")),
    );

    const client = createApiClient("http://localhost:8000/api");

    await expect(client.listDocuments()).rejects.toMatchObject({
      name: "ApiClientError",
      kind: "network",
      status: null,
    });
  });

  it("uploads PDFs with FormData without setting multipart content type", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          id: 8,
          original_filename: "guide.pdf",
          status: "processed",
          error_message: null,
          created_at: "2026-10-03T12:00:00Z",
          updated_at: "2026-10-03T12:01:00Z",
        },
        { status: 201 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = createApiClient("http://localhost:8000/api");
    const file = new File(["%PDF-1.7"], "guide.pdf", {
      type: "application/pdf",
    });

    const result = await client.uploadDocument(file);

    expect(result.id).toBe(8);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.headers).toEqual({
      Accept: "application/json",
    });

    const formData = init.body as FormData;
    expect(formData.get("file")).toBe(file);
  });

  it("accepts 204 responses for document deletion", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(null, { status: 204 }),
      ),
    );

    const client = createApiClient("http://localhost:8000/api");

    await expect(client.deleteDocument(12)).resolves.toBeUndefined();
  });

  it("sends chat questions as JSON and maps sources", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        answer: "The warranty is 24 months.",
        sources: [
          {
            document_id: 3,
            document: "manual.pdf",
            page: 17,
          },
        ],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = createApiClient("http://localhost:8000/api");
    const result = await client.sendChat({
      question: "What is the warranty?",
    });

    expect(result.sources).toEqual([
      {
        document_id: 3,
        document: "manual.pdf",
        page: 17,
      },
    ]);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
    });
    expect(init.body).toBe(
      JSON.stringify({ question: "What is the warranty?" }),
    );
  });

  it("maps request timeouts separately from network failures", async () => {
    vi.useFakeTimers();

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(
        (_url: string, init: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init.signal?.addEventListener(
              "abort",
              () => reject(new DOMException("Aborted", "AbortError")),
              { once: true },
            );
          }),
      ),
    );

    const client = createApiClient("http://localhost:8000/api");
    const request = client.listDocuments(50, { timeoutMs: 25 });

    // Register the rejection assertion before ticking the fake clock so
    // Node never reports the timeout as an unhandled promise rejection.
    const rejectedRequest = expect(request).rejects.toMatchObject({
      name: "ApiClientError",
      kind: "timeout",
      message: "The request timed out",
    });

    await vi.advanceTimersByTimeAsync(25);
    await rejectedRequest;
  });

  it("supports caller cancellation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(
        (_url: string, init: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init.signal?.addEventListener(
              "abort",
              () => reject(new DOMException("Aborted", "AbortError")),
              { once: true },
            );
          }),
      ),
    );

    const controller = new AbortController();
    const client = createApiClient("http://localhost:8000/api");
    const request = client.listDocuments(50, {
      signal: controller.signal,
    });

    controller.abort();

    await expect(request).rejects.toMatchObject({
      name: "ApiClientError",
      kind: "cancelled",
      message: "The request was cancelled",
    });
  });

  it("rejects invalid timeout configuration before fetch", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const client = createApiClient("http://localhost:8000/api");

    await expect(
      client.listDocuments(50, { timeoutMs: 0 }),
    ).rejects.toBeInstanceOf(ApiClientError);

    await expect(
      client.listDocuments(50, { timeoutMs: 0 }),
    ).rejects.toMatchObject({
      kind: "configuration",
    });

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects invalid successful JSON responses predictably", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("not-json", {
          status: 200,
          headers: {
            "Content-Type": "application/json",
          },
        }),
      ),
    );

    const client = createApiClient("http://localhost:8000/api");

    await expect(client.listDocuments()).rejects.toMatchObject({
      kind: "invalid_response",
      status: 200,
    });
  });
});
