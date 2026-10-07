import "server-only";

/** Cliente da API pública da loja (só no servidor; a mesma imagem serve staging e produção). */

export type Color = { material_id: number; name: string; hex: string; kind: string };
export type Niche = { slug: string; name: string; products: number };
export type ProductCard = {
  slug: string;
  title: string;
  niche: string;
  category: string;
  customizable: boolean;
  price_from: string | null;
  colors: string[];
};
export type Variant = {
  id: number;
  sku: string;
  label: string;
  finish: string;
  price_pix: string | null;
  price_card: string | null;
  colors: Color[];
};
export type Product = ProductCard & {
  description: string | null;
  tags: string[];
  disclaimers: string[];
  attribution: string | null;
  age_rating: string | null;
  variants: Variant[];
  parametric_model: string | null;
};
export type CartLine = {
  variant_id: number;
  product_slug: string;
  title: string;
  quantity: number;
  material_id: number | null;
  color: Color | null;
  personalization: Record<string, string>;
  unit_price: string | null;
  line_total: string | null;
};
export type Cart = { token: string; items: CartLine[]; subtotal: string; purchasable: boolean; problems: string[] };
export type ShippingOption = { id: "local" | "retirada" | "envio"; label: string; price: string | null; detail: string };
export type ShippingQuote = {
  cep: string;
  city: string;
  uf: string;
  local: boolean;
  options: ShippingOption[];
  free_shipping_min: string | null;
  missing_for_free: string | null;
};
export type StoreSettings = { free_shipping_min: string | null; pickup_enabled: boolean; pix_enabled: boolean };
export type Pix = { key: string | null; name: string | null; amount: string };
export type PublicOrder = {
  number: number;
  status: string;
  status_label: string;
  total: string;
  shipping: string;
  items: { title: string; quantity: number; personalization: Record<string, string> }[];
  timeline: { at: string; status: string; label: string; media_url: string | null }[];
  progress: string;
  pix: Pix | null;
};

export class StoreApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

function detailMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg ?? "").filter(Boolean).join(" · ") || fallback;
  return fallback;
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
  if (!res.ok) throw new StoreApiError(detailMessage(body.detail, `erro ${res.status}`), res.status);
  return body as T;
}

export async function storeApiOrNull<T>(path: string, revalidate?: number): Promise<T | null> {
  try {
    return await storeApi<T>(path, { revalidate });
  } catch {
    return null;
  }
}
