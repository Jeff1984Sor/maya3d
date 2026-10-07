"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { StoreApiError, storeApi, type Cart, type ShippingQuote } from "@/lib/store";

const COOKIE = "p3d_cart";

async function cartToken(): Promise<string> {
  const jar = await cookies();
  const existing = jar.get(COOKIE)?.value;
  if (existing) {
    try {
      await storeApi<Cart>(`/cart/${existing}`);
      return existing;
    } catch {
      /* carrinho expirou: cria outro */
    }
  }
  const cart = await storeApi<Cart>("/cart", { method: "POST" });
  jar.set(COOKIE, cart.token, { httpOnly: true, sameSite: "lax", maxAge: 60 * 60 * 24 * 30, path: "/" });
  return cart.token;
}

export async function currentCart(): Promise<Cart | null> {
  const token = (await cookies()).get(COOKIE)?.value;
  if (!token) return null;
  try {
    return await storeApi<Cart>(`/cart/${token}`);
  } catch {
    return null;
  }
}

type Line = { variant_id: number; quantity: number; material_id: number | null; personalization: Record<string, string> };

function toLines(cart: Cart): Line[] {
  return cart.items.map((i) => ({
    variant_id: i.variant_id,
    quantity: i.quantity,
    material_id: i.material_id,
    personalization: i.personalization,
  }));
}

async function save(token: string, items: Line[]): Promise<Cart> {
  return storeApi<Cart>(`/cart/${token}`, { method: "PUT", body: JSON.stringify({ items }) });
}

export type AddState = { error?: string; ok?: boolean };

export async function addToCart(_prev: AddState, form: FormData): Promise<AddState> {
  const token = await cartToken();
  const personalization: Record<string, string> = {};
  for (const [key, value] of form.entries()) {
    if (key.startsWith("p_") && String(value).trim()) personalization[key.slice(2)] = String(value).trim();
  }
  const line: Line = {
    variant_id: Number(form.get("variant_id")),
    quantity: Math.max(1, Number(form.get("quantity") || 1)),
    material_id: Number(form.get("material_id")) || null,
    personalization,
  };
  try {
    const cart = await storeApi<Cart>(`/cart/${token}`);
    await save(token, [...toLines(cart), line]);
  } catch (error) {
    return { error: error instanceof StoreApiError ? error.message : "Não foi possível adicionar agora." };
  }
  revalidatePath("/carrinho");
  redirect("/carrinho");
}

export async function updateQuantity(index: number, quantity: number): Promise<void> {
  const token = await cartToken();
  const cart = await storeApi<Cart>(`/cart/${token}`);
  const lines = toLines(cart);
  if (quantity <= 0) lines.splice(index, 1);
  else if (lines[index]) lines[index] = { ...lines[index], quantity };
  await save(token, lines);
  revalidatePath("/carrinho");
}

export type ShippingState = { quote?: ShippingQuote; error?: string };

export async function quoteShipping(_prev: ShippingState, form: FormData): Promise<ShippingState> {
  const cart = await currentCart();
  try {
    const quote = await storeApi<ShippingQuote>("/shipping", {
      method: "POST",
      // com o carrinho, a API cota Correios/transportadoras com medidas e peso reais
      body: JSON.stringify({ cep: String(form.get("cep") ?? ""), subtotal: cart?.subtotal ?? "0", cart_token: cart?.token ?? null }),
    });
    (await cookies()).set("p3d_cep", quote.cep, { httpOnly: true, sameSite: "lax", maxAge: 60 * 60 * 24 * 90, path: "/" });
    return { quote };
  } catch (error) {
    return { error: error instanceof StoreApiError ? error.message : "Não foi possível calcular agora." };
  }
}
