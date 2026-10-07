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

// --- ✍️ Redator por canal ------------------------------------------------------------------
export type ChannelCopy = {
  id: number;
  product_id: number;
  channel: "site" | "mercadolivre" | "shopee" | "instagram";
  title: string;
  description: string;
  bullets: string[];
  keywords: string[];
  hashtags: string[];
  status: "rascunho" | "aprovado" | "descartado";
  guardian_status: string;
  issues: string[];
  model: string | null;
  title_max: number;
};

const errMsg = (error: unknown, fallback: string) => (error instanceof AdminApiError ? error.message : fallback);
const lines = (f: FormData, k: string) =>
  String(f.get(k) ?? "")
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);

function backToProduct(productId: number, key: "ok" | "erro", msg: string): never {
  revalidatePath(`/produtos/${productId}`);
  redirect(`/produtos/${productId}?${key}=${encodeURIComponent(msg)}#textos`);
}

export async function generateCopy(productId: number, form: FormData): Promise<void> {
  await requireSession();
  const channels = form.getAll("channels").map(String);
  try {
    await api.post("/ai/channel-copy", { product_id: productId, channels });
  } catch (error) {
    backToProduct(productId, "erro", errMsg(error, "Falha ao falar com a IA."));
  }
  backToProduct(productId, "ok", "Textos gerados. Revise e aprove cada canal.");
}

export async function editCopy(productId: number, copyId: number, form: FormData): Promise<void> {
  await requireSession();
  try {
    await api.patch(`/ai/channel-copy/${copyId}`, {
      title: String(form.get("title") ?? "").trim(),
      description: String(form.get("description") ?? "").trim(),
      bullets: lines(form, "bullets"),
      keywords: lines(form, "keywords"),
      hashtags: lines(form, "hashtags"),
    });
  } catch (error) {
    backToProduct(productId, "erro", errMsg(error, "Falha ao salvar o texto."));
  }
  backToProduct(productId, "ok", "Texto salvo e conferido de novo.");
}

export async function setCopyStatus(productId: number, copyId: number, status: "aprovado" | "descartado" | "rascunho"): Promise<void> {
  await requireSession();
  try {
    await api.post(`/ai/channel-copy/${copyId}/status`, { status });
  } catch (error) {
    backToProduct(productId, "erro", errMsg(error, "Falha ao mudar o status."));
  }
  backToProduct(productId, "ok", status === "aprovado" ? "Texto aprovado." : `Texto: ${status}.`);
}

export async function applyCopy(productId: number, copyId: number): Promise<void> {
  await requireSession();
  try {
    await api.post(`/ai/channel-copy/${copyId}/apply`, {});
  } catch (error) {
    backToProduct(productId, "erro", errMsg(error, "Falha ao aplicar."));
  }
  revalidatePath("/produtos");
  backToProduct(productId, "ok", "Título e descrição da loja atualizados. O Guardião verificou de novo.");
}

// --- 🔎 Busca semântica --------------------------------------------------------------------
export async function reindexSearch(): Promise<void> {
  await requireSession();
  let done = 0;
  try {
    ({ done } = await api.post<{ done: number }>("/ai/search/reindex", {}));
  } catch (error) {
    redirect(`/ia?erro=${encodeURIComponent(errMsg(error, "Falha ao indexar."))}`);
  }
  revalidatePath("/ia");
  redirect(`/ia?ok=${encodeURIComponent(`${done} produto(s) indexado(s).`)}`);
}
