import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { currentCart } from "@/actions/cart";
import { Container } from "@/components/shop";
import { money } from "@/lib/format";
import { CheckoutForm } from "./checkout-form";

export const metadata: Metadata = { title: "Finalizar compra" };
export const dynamic = "force-dynamic";

export default async function CheckoutPage() {
  const cart = await currentCart();
  if (!cart || !cart.purchasable) redirect("/carrinho");
  return (
    <Container className="grid gap-10 py-10 lg:grid-cols-[1fr_20rem]">
      <div>
        <h1 className="mb-6 font-heading text-3xl font-bold">Finalizar compra</h1>
        <CheckoutForm />
      </div>
      <aside className="h-fit rounded-2xl border border-border bg-surface p-5 text-sm">
        <p className="mb-3 font-medium">Resumo</p>
        <ul className="space-y-2">
          {cart.items.map((i, n) => (
            <li key={n} className="flex justify-between gap-2">
              <span>
                {i.quantity}× {i.title}
              </span>
              <span>{money(i.line_total)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 flex justify-between border-t border-border pt-3 text-base font-semibold">
          <span>Subtotal no Pix</span>
          <span>{money(cart.subtotal)}</span>
        </p>
        <p className="mt-2 text-xs text-muted">A entrega é somada no próximo passo, conforme o CEP.</p>
      </aside>
    </Container>
  );
}
