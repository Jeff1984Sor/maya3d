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
      }),
    }));
  } catch (error) {
    return { error: error instanceof StoreApiError ? error.message : "Não foi possível finalizar agora." };
  }
  redirect(`/pedido/${publicToken}`);
}
