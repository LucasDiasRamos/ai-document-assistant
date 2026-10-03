export type ApiEnvironment = {
  VITE_API_BASE_URL?: string;
};

export function resolveApiBaseUrl(env: ApiEnvironment): string {
  const value = env.VITE_API_BASE_URL?.trim();

  if (!value) {
    throw new Error("VITE_API_BASE_URL is required");
  }

  let url: URL;

  try {
    url = new URL(value);
  } catch {
    throw new Error("VITE_API_BASE_URL must be a valid absolute URL");
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("VITE_API_BASE_URL must use http or https");
  }

  return value.replace(/\/+$/, "");
}
