import { resolveApiBaseUrl } from "./env";

export const apiBaseUrl = resolveApiBaseUrl(import.meta.env);
