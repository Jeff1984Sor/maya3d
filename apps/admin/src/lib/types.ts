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

export interface ModelInfo {
  slug: string;
  title: string;
  niche: string;
  description: string;
  params_schema: { properties?: Record<string, Record<string, unknown>> };
}
