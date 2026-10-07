/**
 * Contratos da API pública da loja (/v1/store). Usados pela vitrine (Next) e pelo app (Expo):
 * uma definição só. Valores em dinheiro chegam como string decimal (ex.: "49.90").
 */

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
  image?: string | null;
};
export type StoreImage = { url: string; thumb: string; alt: string | null };
export type PageLink = { slug: string; title: string };
export type Home = {
  announcement: string | null;
  hero: { title?: string | null; subtitle?: string | null; image?: string | null; cta_label?: string | null; cta_href?: string | null };
  sections: { title: string; href: string | null; products: ProductCard[] }[];
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
  images?: StoreImage[];
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
export type ShippingOption = { id: string; label: string; price: string | null; detail: string }; // me-<id> = Melhor Envio
export type ShippingQuote = {
  cep: string;
  city: string;
  uf: string;
  local: boolean;
  options: ShippingOption[];
  free_shipping_min: string | null;
  missing_for_free: string | null;
};
export type StoreSettings = {
  free_shipping_min: string | null;
  pickup_enabled: boolean;
  pix_enabled: boolean;
  assistant_enabled?: boolean;
};
export type Pix = {
  key: string | null;
  name: string | null;
  amount: string;
  /** Pix pelo gateway: QR Code + copia e cola, confirmação automática. */
  automatic?: boolean;
  qr_code?: string | null;
  qr_code_base64?: string | null;
  expires_at?: string | null;
};
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
export type AssistantTurn = { role: "user" | "assistant"; content: string };
export type AssistantAnswer = { reply: string; products: ProductCard[]; suggestions: string[] };
export type CheckoutResult = { order_number: number; public_token: string; total: string; shipping_pending: boolean; pix: Pix };

/** Erro da API: "detail" do FastAPI (texto ou lista de validações) vira frase legível. */
export function storeErrorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg ?? "").filter(Boolean).join(" · ") || fallback;
  return fallback;
}

/** Caminho público de imagem da loja (/m/<chave>) → endereço na API (app fala direto com ela). */
export function apiMediaUrl(apiBase: string, path: string | null | undefined): string | null {
  if (!path) return null;
  if (/^https?:\/\//.test(path)) return path;
  return path.startsWith("/m/") ? `${apiBase.replace(/\/+$/, "")}/v1/store/media/${path.slice(3)}` : null;
}
