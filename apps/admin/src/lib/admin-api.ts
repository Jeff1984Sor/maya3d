import "server-only";

/**
 * Cliente das rotas /v1/admin da API. Só no servidor: o token nunca chega ao navegador.
 */

export class AdminApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "AdminApiError";
  }
}

type Detail = string | { loc?: (string | number)[]; msg?: string }[] | undefined;

/** Converte o erro do FastAPI (string ou lista de validações) em frase legível. */
export function formatDetail(detail: Detail, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => {
        const field = d.loc?.filter((p) => p !== "body").join(".");
        return field ? `${field}: ${d.msg}` : (d.msg ?? "");
      })
      .join(" · ");
  }
  return fallback;
}

export async function adminApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}/v1/admin${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      accept: "application/json",
      ...(init.body && !(init.body instanceof FormData) ? { "content-type": "application/json" } : {}),
      "x-admin-token": process.env.ADMIN_API_TOKEN ?? "",
      ...init.headers,
    },
    signal: AbortSignal.timeout(15000),
  });
  if (res.status === 204) return undefined as T;
  const body = (await res.json().catch(() => ({}))) as { detail?: Detail };
  if (!res.ok) throw new AdminApiError(formatDetail(body.detail, `erro ${res.status}`), res.status);
  return body as T;
}

export const api = {
  get: <T>(path: string) => adminApi<T>(path),
  post: <T>(path: string, data: unknown) => adminApi<T>(path, { method: "POST", body: JSON.stringify(data) }),
  put: <T>(path: string, data: unknown) => adminApi<T>(path, { method: "PUT", body: JSON.stringify(data) }),
  patch: <T>(path: string, data: unknown) => adminApi<T>(path, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (path: string) => adminApi<void>(path, { method: "DELETE" }),
};
