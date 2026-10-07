import { FALLBACK_BRAND, type BrandPublic } from "./brand";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ReadyResponse {
  status: "ok" | "degraded";
  checks: Record<string, { ok: boolean; detail: string }>;
}

export interface ApiClientOptions {
  baseUrl: string;
  /** Opções extras do fetch (ex.: `{ next: { revalidate: 60 } }` no Next). */
  init?: RequestInit & { next?: { revalidate?: number | false; tags?: string[] } };
  fetch?: typeof fetch;
  timeoutMs?: number;
}

export function createApiClient({ baseUrl, init, fetch: fetchImpl = fetch, timeoutMs = 3000 }: ApiClientOptions) {
  const root = baseUrl.replace(/\/+$/, "");

  async function request<T>(path: string, acceptStatuses: number[] = []): Promise<T> {
    const res = await fetchImpl(`${root}${path}`, {
      ...init,
      headers: { accept: "application/json", ...init?.headers },
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok && !acceptStatuses.includes(res.status)) {
      throw new ApiError(`GET ${path} falhou`, res.status);
    }
    return (await res.json()) as T;
  }

  return {
    getBrand: () => request<BrandPublic>("/v1/brand"),
    /** 503 também traz corpo útil (qual dependência caiu). */
    getReady: () => request<ReadyResponse>("/health/ready", [503]),

    /** Nunca lança: a vitrine precisa renderizar mesmo com a API fora. */
    async getBrandOrFallback(): Promise<BrandPublic> {
      try {
        return await request<BrandPublic>("/v1/brand");
      } catch {
        return FALLBACK_BRAND;
      }
    },
    async getReadyOrNull(): Promise<ReadyResponse | null> {
      try {
        return await request<ReadyResponse>("/health/ready", [503]);
      } catch {
        return null;
      }
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
