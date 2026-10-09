export type ApiEnvironment = {
  VITE_API_BASE_URL?: string;
};

export function resolveApiBaseUrl(env: ApiEnvironment): string {
  const value = env.VITE_API_BASE_URL?.trim();

  if (!value) {
    throw new Error("VITE_API_BASE_URL is required");
  }

  if (value.startsWith("/")) {
    if (value.startsWith("//")) {
      throw new Error(
        "VITE_API_BASE_URL must be a root-relative path or http(s) URL",
      );
    }

    return value === "/" ? "" : value.replace(/\/+$/, "");
  }

  // URL() treats "localhost:8000" as a custom URI scheme; require
  // explicit protocol separators for absolute API addresses.
  if (!value.includes("://")) {
    throw new Error(
      "VITE_API_BASE_URL must be a root-relative path or valid absolute URL",
    );
  }

  let url: URL;

  try {
    url = new URL(value);
  } catch {
    throw new Error(
      "VITE_API_BASE_URL must be a root-relative path or valid absolute URL",
    );
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("VITE_API_BASE_URL must use http or https");
  }

  return value.replace(/\/+$/, "");
}
