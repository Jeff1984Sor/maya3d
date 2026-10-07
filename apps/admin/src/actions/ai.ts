"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

export type Suggestion = {
  title: string;
  title_short: string;
  category: string;
  subcategory: string | null;
  description: string;
  bullets: string[];
  faq: { question: string; answer: string }[];
  tags: string[];
  occasions: string[];
  color_ideas: string[];
  seo_title: string;
  seo_description: string;
};

export type EnrichState = {
  suggestion?: Suggestion;
  approved?: boolean;
  violations?: { code: string; message: string }[];
  error?: string;
};

export async function enrichProduct(hint: string, niche: string): Promise<EnrichState> {
  await requireSession();
  try {
    const r = await api.post<{ suggestion: Suggestion; guardian_approved: boolean; violations: { code: string; message: string }[] }>(
      "/ai/enrich-product",
      { hint, niche },
    );
    return { suggestion: r.suggestion, approved: r.guardian_approved, violations: r.violations };
  } catch (error) {
    return { error: error instanceof AdminApiError ? error.message : "Falha ao falar com a IA." };
  }
}

export async function saveAiConfig(form: FormData): Promise<void> {
  await requireSession();
  const pick = (k: string) => String(form.get(k) ?? "").trim() || null;
  try {
    await api.put("/ai/config", {
      model_default: pick("model_default"),
      model_guardian: pick("model_guardian"),
      model_personalizer: pick("model_personalizer"),
      model_embedding: pick("model_embedding"),
      daily_budget_usd: String(form.get("daily_budget_usd") ?? "5").replace(",", "."),
    });
  } catch (error) {
    redirect(`/ia?erro=${encodeURIComponent(error instanceof AdminApiError ? error.message : "Falha ao salvar.")}`);
  }
  revalidatePath("/ia");
  redirect(`/ia?ok=${encodeURIComponent("Modelos salvos.")}`);
}
