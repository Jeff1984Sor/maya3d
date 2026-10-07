"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

function fail(path: string, error: unknown): never {
  const msg = error instanceof AdminApiError ? error.message : "Falha ao falar com a API.";
  redirect(`${path}${path.includes("?") ? "&" : "?"}erro=${encodeURIComponent(msg)}`);
}

/** Avança o status (botões da Produção e do pedido). `back` = tela para onde voltar. */
export async function advanceOrder(orderId: number, to: string, back: string, form?: FormData): Promise<void> {
  await requireSession();
  const note = String(form?.get("note") ?? "").trim() || null;
  const media = String(form?.get("media_url") ?? "").trim() || null;
  try {
    await api.post(`/orders/${orderId}/advance`, { to, note, media_url: media });
  } catch (error) {
    fail(back, error);
  }
  revalidatePath("/producao");
  revalidatePath("/pedidos");
  revalidatePath(`/pedidos/${orderId}`);
  redirect(back);
}

export async function jobAction(jobId: number, action: "iniciar" | "concluir" | "falhou", back: string, form?: FormData) {
  await requireSession();
  const reason = String(form?.get("reason") ?? "").trim() || null;
  try {
    await api.post(`/print-jobs/${jobId}`, { action, reason });
  } catch (error) {
    fail(back, error);
  }
  revalidatePath("/fila");
  revalidatePath("/producao");
  redirect(back);
}

/** Lança uma venda manual (B2B, balcão ou teste do fluxo). */
export async function createManualOrder(form: FormData): Promise<void> {
  await requireSession();
  const variant = Number(form.get("variant_id"));
  const material = Number(form.get("material_id"));
  const personalization = String(form.get("personalization") ?? "").trim();
  let id: number;
  try {
    ({ id } = await api.post<{ id: number }>("/orders", {
      channel: String(form.get("channel") ?? "manual"),
      customer_id: Number(form.get("customer_id")) || null,
      promised_date: String(form.get("promised_date") ?? "") || null,
      items: [
        {
          variant_id: variant || null,
          title: String(form.get("title") ?? "").trim() || null,
          quantity: Number(form.get("quantity")),
          unit_price: String(form.get("unit_price") ?? "0").replace(",", "."),
          personalization: personalization ? { texto: personalization } : {},
          material_ids: material ? [material] : [],
        },
      ],
    }));
  } catch (error) {
    fail("/pedidos", error);
  }
  revalidatePath("/pedidos");
  redirect(`/pedidos/${id}`);
}
