"use server";

import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";
import type { GuardianResult, QuoteResponse } from "@/lib/types";

export type ToolState<T> = { result?: T; error?: string };

function messageOf(error: unknown): string {
  return error instanceof AdminApiError ? error.message : "Falha inesperada ao falar com a API.";
}

const dec = (v: FormDataEntryValue | null) => String(v ?? "").trim().replace(",", ".");
const list = (v: FormDataEntryValue | null) =>
  String(v ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

export async function runQuote(_prev: ToolState<QuoteResponse>, form: FormData): Promise<ToolState<QuoteResponse>> {
  await requireSession();
  const grams: Record<string, string> = {};
  for (const i of [1, 2, 3]) {
    const material = String(form.get(`material_${i}`) ?? "");
    const g = dec(form.get(`grams_${i}`));
    if (material && g) grams[material] = g;
  }
  if (Object.keys(grams).length === 0) return { error: "Informe ao menos um material com gramas." };

  const shipping = dec(form.get("shipping"));
  const channels = list(form.get("channels"));
  try {
    const result = await api.post<QuoteResponse>("/pricing/quote", {
      grams_by_material: grams,
      print_minutes: Math.round(Number(dec(form.get("print_hours"))) * 60),
      printer_id: Number(form.get("printer_id")),
      post_minutes: Number(form.get("post_minutes") || 0),
      category: String(form.get("category") ?? "").trim() || null,
      extra_costs: dec(form.get("extra_costs")) || "0",
      ...(channels.length ? { channels } : {}),
      ...(shipping ? { shipping_by_channel: Object.fromEntries(channels.map((c) => [c, shipping])) } : {}),
    });
    return { result };
  } catch (error) {
    return { error: messageOf(error) };
  }
}

export async function runGuardian(_prev: ToolState<GuardianResult>, form: FormData): Promise<ToolState<GuardianResult>> {
  await requireSession();
  const text = (k: string) => String(form.get(k) ?? "").trim();
  try {
    const result = await api.post<GuardianResult>("/guardian/check", {
      niche: text("niche"),
      title: text("title"),
      description: text("description"),
      tags: list(form.get("tags")),
      occasions: list(form.get("occasions")),
      origin: text("origin") || "outro",
      license: text("license") || null,
      author: text("author") || null,
      material_kinds: form.getAll("material_kinds").map(String),
      customer_text: list(form.get("customer_text")),
      channel: text("channel") || null,
    });
    return { result };
  } catch (error) {
    return { error: messageOf(error) };
  }
}

export type CompareResult = {
  reference: string;
  reference_grams: string;
  rows: {
    material_id: number;
    label: string;
    kind: string;
    color_hex: string;
    density: string;
    grams: string;
    cost: QuoteResponse["cost"];
    quotes: QuoteResponse["quotes"];
    warnings: string[];
    best_price: string | null;
    best_profit: string | null;
  }[];
};

export async function runCompare(_prev: ToolState<CompareResult>, form: FormData): Promise<ToolState<CompareResult>> {
  await requireSession();
  const channels = list(form.get("channels"));
  try {
    const result = await api.post<CompareResult>("/pricing/compare", {
      reference_material_id: Number(form.get("reference_material_id")),
      grams: dec(form.get("grams")),
      print_minutes: Math.max(1, Math.round(Number(dec(form.get("print_hours"))) * 60)),
      printer_id: Number(form.get("printer_id")),
      post_minutes: Number(form.get("post_minutes") || 0),
      category: String(form.get("category") ?? "").trim() || null,
      extra_costs: dec(form.get("extra_costs")) || "0",
      ...(channels.length ? { channels } : {}),
    });
    return { result };
  } catch (error) {
    return { error: messageOf(error) };
  }
}
