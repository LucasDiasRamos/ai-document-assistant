import { describe, expect, it } from "vitest";

import { resolveApiBaseUrl } from "./env";

describe("resolveApiBaseUrl", () => {
  it("returns a normalized absolute API URL", () => {
    expect(
      resolveApiBaseUrl({
        VITE_API_BASE_URL: " http://localhost:8000/ ",
      }),
    ).toBe("http://localhost:8000");
  });

  it("rejects a missing API URL", () => {
    expect(() => resolveApiBaseUrl({})).toThrow(
      "VITE_API_BASE_URL is required",
    );
  });

  it("rejects a relative API URL", () => {
    expect(() =>
      resolveApiBaseUrl({ VITE_API_BASE_URL: "/api" }),
    ).toThrow("VITE_API_BASE_URL must be a valid absolute URL");
  });

  it("rejects unsupported protocols", () => {
    expect(() =>
      resolveApiBaseUrl({
        VITE_API_BASE_URL: "file:///tmp/api",
      }),
    ).toThrow("VITE_API_BASE_URL must use http or https");
  });
});
