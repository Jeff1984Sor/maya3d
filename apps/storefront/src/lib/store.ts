import "server-only";

/** Cliente da API pública da loja (só no servidor; a mesma imagem serve staging e produção). */

export type {
  Cart,
  CartLine,
  Color,
  Home,
  Niche,
  PageLink,
  Pix,
  Product,
  ProductCard,
  PublicOrder,
  ShippingOption,
  ShippingQuote,
  StoreImage,
  StoreSettings,
  Variant,
} from "@print3d/shared";
import { storeErrorMessage } from "@print3d/shared";

export class StoreApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function storeApi<T>(path: string, init: RequestInit & { revalidate?: number } = {}): Promise<T> {
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const { revalidate, ...rest } = init;
  const res = await fetch(`${base}/v1/store${path}`, {
    ...rest,
    headers: { accept: "application/json", ...(rest.body ? { "content-type": "application/json" } : {}), ...rest.headers },
    ...(revalidate !== undefined ? { next: { revalidate } } : { cache: "no-store" as const }),
    signal: AbortSignal.timeout(10000),
  });
  const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
  if (!res.ok) throw new StoreApiError(storeErrorMessage(body.detail, `erro ${res.status}`), res.status);
  return body as T;
}

export async function storeApiOrNull<T>(path: string, revalidate?: number): Promise<T | null> {
  try {
    return await storeApi<T>(path, { revalidate });
  } catch {
    return null;
  }
}
