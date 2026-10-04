import { describe, expect, it } from "vitest";

import { resolveApiBaseUrl } from "./env";

describe("resolveApiBaseUrl", () => {
  it("returns a normalized absolute API URL", () => {
    expect(
      resolveApiBaseUrl({
        VITE_API_BASE_URL: " http://localhost:8000/api/ ",
      }),
    ).toBe("http://localhost:8000/api");
  });

  it("accepts a normalized same-origin root-relative API path", () => {
    expect(
      resolveApiBaseUrl({
        VITE_API_BASE_URL: " /api/ ",
      }),
    ).toBe("/api");
  });

  it("rejects a missing API URL", () => {
    expect(() => resolveApiBaseUrl({})).toThrow(
      "VITE_API_BASE_URL is required",
    );
  });

  it("rejects protocol-relative URLs", () => {
    expect(() =>
      resolveApiBaseUrl({
        VITE_API_BASE_URL: "//example.com/api",
      }),
    ).toThrow(
      "VITE_API_BASE_URL must be a root-relative path or http(s) URL",
    );
  });

  it("rejects malformed non-relative API URLs", () => {
    expect(() =>
      resolveApiBaseUrl({
        VITE_API_BASE_URL: "localhost:8000/api",
      }),
    ).toThrow(
      "VITE_API_BASE_URL must be a root-relative path or valid absolute URL",
    );
  });

  it("rejects unsupported protocols", () => {
    expect(() =>
      resolveApiBaseUrl({
        VITE_API_BASE_URL: "file:///tmp/api",
      }),
    ).toThrow("VITE_API_BASE_URL must use http or https");
  });
});
