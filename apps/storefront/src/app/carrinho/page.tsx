import type { Metadata } from "next";
import Link from "next/link";
import { currentCart, updateQuantity } from "@/actions/cart";
import { Container } from "@/components/shop";
import { money } from "@/lib/format";
import { ShippingCalc } from "./shipping-calc";

export const metadata: Metadata = { title: "Carrinho" };
export const dynamic = "force-dynamic";

export default async function CarrinhoPage() {
  const cart = await currentCart();
  const items = cart?.items ?? [];

  if (items.length === 0) {
    return (
      <Container className="py-20 text-center">
        <h1 className="font-heading text-3xl font-bold">Seu carrinho está vazio</h1>
        <Link href="/busca" className="mt-6 inline-block rounded-xl bg-primary px-6 py-3 font-medium text-white">
          Ver produtos
        </Link>
      </Container>
    );
  }

  return (
    <Container className="grid gap-10 py-10 lg:grid-cols-[1fr_22rem]">
      <div>
        <h1 className="mb-6 font-heading text-3xl font-bold">Carrinho</h1>
        <ul className="divide-y divide-border rounded-2xl border border-border bg-surface">
          {items.map((item, index) => (
            <li key={index} className="flex flex-wrap items-center gap-4 p-4">
              <div className="min-w-0 flex-1">
                <Link href={`/p/${item.product_slug}`} className="font-medium hover:text-primary">
                  {item.title}
                </Link>
                <p className="text-xs text-muted">
                  {item.color && (
                    <>
                      <span className="mr-1 inline-block size-3 rounded-full border border-border align-middle" style={{ background: item.color.hex }} />
                      {item.color.name}
                    </>
                  )}
                  {Object.entries(item.personalization)
                    .filter(([, v]) => v)
                    .map(([k, v]) => ` · ${k}: ${v}`)
                    .join("")}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <form action={updateQuantity.bind(null, index, item.quantity - 1)}>
                  <button className="size-8 rounded-lg border border-border">−</button>
                </form>
                <span className="w-8 text-center">{item.quantity}</span>
                <form action={updateQuantity.bind(null, index, item.quantity + 1)}>
                  <button className="size-8 rounded-lg border border-border">+</button>
                </form>
              </div>
              <p className="w-24 text-right font-semibold">{money(item.line_total)}</p>
              <form action={updateQuantity.bind(null, index, 0)}>
                <button className="text-xs text-muted hover:text-primary">remover</button>
              </form>
            </li>
          ))}
        </ul>
        {cart?.problems.map((p) => (
          <p key={p} className="mt-3 rounded-xl bg-primary/10 p-3 text-sm text-primary">
            {p}
          </p>
        ))}
      </div>

      <aside className="space-y-4">
        <div className="rounded-2xl border border-border bg-surface p-5">
          <div className="flex justify-between text-lg">
            <span>Subtotal (Pix)</span>
            <span className="font-heading font-bold">{money(cart?.subtotal)}</span>
          </div>
          <ShippingCalc />
          <Link
            href={cart?.purchasable ? "/checkout" : "#"}
            aria-disabled={!cart?.purchasable}
            className={`mt-5 block rounded-xl px-6 py-3 text-center font-semibold text-white ${cart?.purchasable ? "bg-primary hover:opacity-90" : "pointer-events-none bg-muted"}`}
          >
            Finalizar compra
          </Link>
        </div>
      </aside>
    </Container>
  );
}
