import Constants from "expo-constants";
import { apiMediaUrl, storeErrorMessage } from "@print3d/shared";

/** Endereço da API definido no build (app.config.ts → extra.apiUrl). */
export const API_URL: string = (Constants.expoConfig?.extra?.apiUrl as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

/** Chamada à API pública da loja (/v1/store), com limite de tempo e erro legível. */
export async function store<T>(path: string, init: { method?: string; body?: unknown; timeoutMs?: number } = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), init.timeoutMs ?? 15000);
  try {
    const res = await fetch(`${API_URL}/v1/store${path}`, {
      method: init.method ?? (init.body === undefined ? "GET" : "POST"),
      headers: { accept: "application/json", ...(init.body !== undefined ? { "content-type": "application/json" } : {}) },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      signal: controller.signal,
    });
    const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
    if (!res.ok) throw new ApiError(storeErrorMessage(data.detail, `erro ${res.status}`), res.status);
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError("Sem conexão com a loja. Confira a internet e tente de novo.", 0);
  } finally {
    clearTimeout(timer);
  }
}

export const media = (path: string | null | undefined) => apiMediaUrl(API_URL, path);

export const errorText = (error: unknown) => (error instanceof Error ? error.message : "Algo deu errado.");
