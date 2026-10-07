"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

export type MlStatus = {
  configured: boolean;
  https_ready: boolean;
  pictures_ready: boolean;
  connected: boolean;
  nickname: string | null;
  status: string | null;
  webhook_path: string;
  callback_path: string;
};
export type MlListing = {
  id: number;
  product_id: number;
  variant_id: number;
  external_id: string | null;
  listing_type: string | null;
  price: string;
  status: string;
  permalink: string | null;
  last_error: string | null;
  fee: string | null;
};
export type MlQuestion = { id: number; item_external_id: string | null; product_id: number | null; text: string; status: string; answer: string | null };
export type MlPreview = {
  title: string;
  category: { id: string; name: string };
  fee: string;
  fee_percentage: string | null;
  net: string;
  required_attributes: { id: string; name: string }[];
};

const msg = (e: unknown, f: string) => (e instanceof AdminApiError ? e.message : f);
const go = (path: string, key: "ok" | "erro", m: string): never => redirect(`${path}${path.includes("?") ? "&" : "?"}${key}=${encodeURIComponent(m)}`);

/** Gera o link de autorização e manda o dono para o Mercado Livre. */
export async function connectMl(): Promise<void> {
  await requireSession();
  let url = "";
  try {
    ({ url } = await api.post<{ url: string }>("/mercadolivre/connect", {}));
  } catch (e) {
    go("/mercado-livre", "erro", msg(e, "Falha ao gerar o link."));
  }
  redirect(url);
}

export async function disconnectMl(): Promise<void> {
  await requireSession();
  await api.delete("/mercadolivre/account");
  go("/mercado-livre", "ok", "Conta desconectada.");
}

export async function previewMl(productId: number, form: FormData): Promise<void> {
  await requireSession();
  const back = `/produtos/${productId}`;
  const q = new URLSearchParams({
    ml_variant: String(form.get("variant_id")),
    ml_price: String(form.get("price") ?? "").replace(",", "."),
    ml_type: String(form.get("listing_type") ?? "gold_special"),
  });
  redirect(`${back}?${q.toString()}#ml`);
}

export async function publishMl(productId: number, form: FormData): Promise<void> {
  await requireSession();
  const back = `/produtos/${productId}`;
  const attributes: Record<string, string> = {};
  for (const [k, v] of form.entries()) if (k.startsWith("attr_") && String(v).trim()) attributes[k.slice(5)] = String(v).trim();
  let listing: MlListing | null = null;
  try {
    listing = await api.post<MlListing>("/mercadolivre/listings", {
      variant_id: Number(form.get("variant_id")),
      price: String(form.get("price") ?? "").replace(",", "."),
      listing_type: String(form.get("listing_type") ?? "gold_special"),
      attributes,
    });
  } catch (e) {
    go(back, "erro", msg(e, "Falha ao anunciar."));
  }
  revalidatePath(back);
  if (listing?.status === "publicado") go(back, "ok", "Anúncio publicado no Mercado Livre.");
  go(back, "erro", `O Mercado Livre recusou: ${listing?.last_error ?? "erro desconhecido"}`);
}

export async function answerQuestion(questionId: number, form: FormData): Promise<void> {
  await requireSession();
  try {
    await api.post(`/mercadolivre/questions/${questionId}/answer`, { text: String(form.get("text") ?? "").trim() });
  } catch (e) {
    go("/mercado-livre", "erro", msg(e, "Falha ao responder."));
  }
  revalidatePath("/mercado-livre");
  go("/mercado-livre", "ok", "Resposta enviada pelo Mercado Livre.");
}
