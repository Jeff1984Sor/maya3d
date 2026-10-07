/** Tipos das respostas da API usadas nas telas (espelham os schemas Pydantic). */

export interface Material {
  id: number;
  kind: string;
  color_name: string;
  color_hex: string;
  price_per_kg: string;
  stock_grams: number;
  low_stock: boolean;
  active: boolean;
}

export interface Printer {
  id: number;
  name: string;
  model: string;
  status: string;
}

export interface Niche {
  id: number;
  slug: string;
  name: string;
  active: boolean;
}

export interface CostConfig {
  energy_price_kwh: string;
  labor_per_hour: string;
  failure_rate: string;
  min_profit: string;
  default_margin: string;
  margin_by_category: Record<string, string>;
  updated_at: string;
}

export interface ChannelQuote {
  channel: string;
  price: string | null;
  commission: string | null;
  fixed_fee: string | null;
  shipping: string;
  net_profit: string | null;
  margin_pct: string | null;
  error: string | null;
}

export interface QuoteResponse {
  cost: Record<"material" | "energy" | "wear" | "labor" | "failure" | "extras" | "total", string>;
  target_profit: string;
  quotes: ChannelQuote[];
  warnings: string[];
}

export interface GuardianResult {
  verdict: "aprovado" | "bloqueado";
  approved: boolean;
  violations: { code: string; message: string; evidence: string }[];
  disclaimers: string[];
  warnings: string[];
  attribution_required: boolean;
  age_rating: string | null;
  audit_id: number;
}

export interface AuditEntry {
  id: number;
  created_at: string;
  actor: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  decision: string | null;
  reason: string | null;
  payload: Record<string, unknown>;
}

export interface ProductSummary {
  id: number;
  slug: string;
  niche: string;
  category: string;
  subcategory: string | null;
  title: string;
  description: string | null;
  tags: string[];
  occasions: string[];
  min_material: string | null;
  customizable: boolean;
  status: "rascunho" | "ativo" | "pausado";
  guardian_status: "aprovado" | "bloqueado" | "pendente";
  guardian_reason: string | null;
  age_rating: string | null;
  updated_at: string;
  variant_count: number;
  available: boolean;
}

export interface Variant {
  id: number;
  sku: string;
  size_label: string | null;
  finish: string;
  grams_by_material: Record<string, number> | null;
  print_seconds: number | null;
  post_minutes: number;
  packaging_id: number | null;
  packed_weight_g: number | null;
  slicing_source: "a_confirmar" | "manual" | "fatiador";
}

export interface ProductDetail extends ProductSummary {
  design: {
    name: string;
    origin: string;
    license: string;
    author: string | null;
    source_url: string | null;
    attribution_text: string | null;
  };
  variants: Variant[];
  disclaimers: string[];
  attribution_required: boolean;
}

export interface VariantQuote {
  ready: boolean;
  reason: string | null;
  cost_total: string | null;
  quotes: ChannelQuote[];
  warnings: string[];
}

export interface ModelInfo {
  slug: string;
  title: string;
  niche: string;
  description: string;
  params_schema: { properties?: Record<string, Record<string, unknown>> };
}

export interface OrderSummary {
  id: number;
  number: number;
  channel: string;
  status: string;
  total: string;
  customer_id: number | null;
  promised_date: string | null;
  local_delivery: boolean;
  created_at: string;
  progress: string;
  next_step: string | null;
}

export interface OrderItem {
  id: number;
  title: string;
  sku: string | null;
  quantity: number;
  unit_price: string;
  personalization: Record<string, unknown>;
  material_ids: number[];
  needs_sample: boolean;
  produced: number;
}

export interface PrintJob {
  id: number;
  order_item_id: number;
  quantity: number;
  is_sample: boolean;
  status: string;
  material_key: string;
  due_date: string | null;
  failure_reason: string | null;
}

export interface OrderDetail extends OrderSummary {
  subtotal: string;
  shipping: string;
  discount: string;
  sample_rounds: number;
  notes: string | null;
  items: OrderItem[];
  events: { created_at: string; status: string; note: string | null; media_url: string | null; actor: string }[];
  jobs: PrintJob[];
  allowed: string[];
  customer: { id: number; name: string; whatsapp: string | null } | null;
}

export interface QueueGroup {
  material_key: string;
  materials: string[];
  total_pieces: number;
  jobs: {
    job_id: number;
    status: string;
    order_id: number;
    order_number: number;
    title: string;
    quantity: number;
    is_sample: boolean;
    due_date: string | null;
    personalization: Record<string, unknown>;
  }[];
}
