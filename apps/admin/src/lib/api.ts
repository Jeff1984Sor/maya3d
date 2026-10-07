import { createApiClient } from "@print3d/shared";

/** Server-side apenas, pela rede interna do compose. Mesma imagem em staging e produção. */
export const api = createApiClient({
  baseUrl: process.env.API_INTERNAL_URL ?? "http://localhost:8000",
  init: { next: { revalidate: 30 } },
});
