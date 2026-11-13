"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { StoreApiError, storeApi } from "@/lib/store";

export type CheckoutState = { error?: string };

export async function placeOrder(_prev: CheckoutState, form: FormData): Promise<CheckoutState> {
  const token = (await cookies()).get("p3d_cart")?.value;
  if (!token) return { error: "Seu carrinho está vazio." };
  const text = (k: string) => String(form.get(k) ?? "").trim();
  let publicToken: string;
  try {
    ({ public_token: publicToken } = await storeApi<{ public_token: string }>("/checkout", {
      method: "POST",
      body: JSON.stringify({
        cart_token: token,
        name: text("name"),
        email: text("email"),
        whatsapp: text("whatsapp"),
        whatsapp_opt_in: form.get("whatsapp_opt_in") === "on",
        marketing_opt_in: form.get("marketing_opt_in") === "on",
        accept_terms: form.get("accept_terms") === "on",
        cep: text("cep"),
        street: text("street"),
        number: text("number"),
        complement: text("complement") || null,
        district: text("district"),
        shipping_option: text("shipping_option"),
        notes: text("notes") || null,
        payment_method: text("payment_method") === "cartao" ? "cartao" : "pix",
      }),
    }));
  } catch (error) {
    return { error: error instanceof StoreApiError ? error.message : "Não foi possível finalizar agora." };
  }
  redirect(`/pedido/${publicToken}`);
}

export type CardData = {
  token: string;
  payment_method_id: string;
  issuer_id?: string | number | null;
  installments: number;
  payer?: { email?: string; identification?: { type?: string; number?: string } };
};
export type CardResult = { status: string; paid: boolean; message: string } | { error: string };

/** Cartão: só o token do formulário do Mercado Pago passa por aqui (nunca o número). */
export async function payCard(orderToken: string, data: CardData): Promise<CardResult> {
  if (!/^[A-Za-z0-9_-]{10,60}$/.test(orderToken)) return { error: "Pedido inválido." };
  try {
    return await storeApi<CardResult>(`/orders/${orderToken}/card`, {
      method: "POST",
      body: JSON.stringify({
        token: data.token,
        payment_method_id: data.payment_method_id,
        issuer_id: data.issuer_id ? String(data.issuer_id) : null,
        installments: Number(data.installments) || 1,
        payer: {
          email: data.payer?.email || null,
          identification: data.payer?.identification?.number
            ? { type: data.payer.identification.type || "CPF", number: data.payer.identification.number }
            : null,
        },
      }),
    });
  } catch (error) {
    return { error: error instanceof StoreApiError ? error.message : "Não foi possível processar o cartão agora." };
  }
}
