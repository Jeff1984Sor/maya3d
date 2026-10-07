import { createApiClient } from "@print3d/shared";

/**
 * Só chamadas server-side, pela rede interna do compose (API_INTERNAL_URL).
 * Nada de NEXT_PUBLIC_*: a mesma imagem Docker serve staging e produção.
 */
export const api = createApiClient({
  baseUrl: process.env.API_INTERNAL_URL ?? "http://localhost:8000",
  init: { next: { revalidate: 30 } },
});
