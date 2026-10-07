"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { MlListing } from "@/actions/mercadolivre";
import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

export type ShopeeStatus = {
  configured: boolean;
  https_ready: boolean;
  connected: boolean;
  shop: string | null;
  status: string | null;
  webhook_path: string;
  callback_path: string;
};

const msg = (e: unknown, f: string) => (e instanceof AdminApiError ? e.message : f);
const go = (path: string, key: "ok" | "erro", m: string): never => redirect(`${path}?${key}=${encodeURIComponent(m)}`);

export async function connectShopee(): Promise<void> {
  await requireSession();
  let url = "";
  try {
    ({ url } = await api.post<{ url: string }>("/shopee/connect", {}));
  } catch (e) {
    go("/shopee", "erro", msg(e, "Falha ao gerar o link."));
  }
  redirect(url);
}

export async function disconnectShopee(): Promise<void> {
  await requireSession();
  await api.delete("/shopee/account");
  go("/shopee", "ok", "Loja desconectada.");
}

export async function publishShopee(productId: number, form: FormData): Promise<void> {
  await requireSession();
  const back = `/produtos/${productId}`;
  let listing: MlListing | null = null;
  try {
    listing = await api.post<MlListing>("/shopee/listings", {
      variant_id: Number(form.get("variant_id")),
      price: String(form.get("price") ?? "").replace(",", "."),
    });
  } catch (e) {
    go(back, "erro", msg(e, "Falha ao anunciar na Shopee."));
  }
  revalidatePath(back);
  if (listing?.status === "publicado") go(back, "ok", "Anúncio publicado na Shopee.");
  go(back, "erro", `A Shopee recusou: ${listing?.last_error ?? "erro desconhecido"}`);
}
