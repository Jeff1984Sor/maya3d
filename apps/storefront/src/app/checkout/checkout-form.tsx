"use client";

import { startTransition, useActionState, useRef, useState } from "react";
import { quoteShipping, type ShippingState } from "@/actions/cart";
import { placeOrder, type CheckoutState } from "@/actions/checkout";
import { money } from "@/lib/format";

const input = "w-full rounded-xl border border-border bg-surface px-3 py-2.5";

export function CheckoutForm({ subtotalPix, subtotalCard }: { subtotalPix: string; subtotalCard: string | null }) {
  const [method, setMethod] = useState<"pix" | "cartao">("pix");
  const [state, action, pending] = useActionState<CheckoutState, FormData>(placeOrder, {});
  const [shipping, quote, quoting] = useActionState<ShippingState, FormData>(quoteShipping, {});
  const [option, setOption] = useState<string>("");
  const lastCep = useRef("");

  // CEP completo: calcula o frete sozinho (o botão "Ver opções" continua para recalcular).
  function autoQuote(value: string) {
    const digits = value.replace(/\D/g, "");
    if (digits.length !== 8 || digits === lastCep.current) return;
    lastCep.current = digits;
    const data = new FormData();
    data.set("cep", digits);
    startTransition(() => quote(data));
  }

  return (
    <form action={action} className="space-y-8">
      <section className="space-y-3">
        <h2 className="font-heading text-lg font-semibold">Seus dados</h2>
        <input name="name" required placeholder="Nome completo" className={input} />
        <div className="grid gap-3 sm:grid-cols-2">
          <input name="email" type="email" required placeholder="E-mail" className={input} />
          <input name="whatsapp" required placeholder="WhatsApp com DDD" inputMode="tel" className={input} />
        </div>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" name="whatsapp_opt_in" defaultChecked className="mt-1 accent-[var(--secondary)]" />
          Quero receber o andamento do pedido pelo WhatsApp
        </label>
      </section>

      <section className="space-y-3">
        <h2 className="font-heading text-lg font-semibold">Entrega</h2>
        <div className="flex gap-2">
          <input name="cep" required placeholder="CEP" inputMode="numeric" maxLength={9} onChange={(e) => autoQuote(e.target.value)} className={input} />
          <button formAction={quote} formNoValidate disabled={quoting} className="rounded-xl border border-border px-4">
            {quoting ? "…" : "Ver opções"}
          </button>
        </div>
        {shipping.error && <p className="text-sm text-primary">{shipping.error}</p>}
        {shipping.quote && (
          <>
            <div className="grid gap-3 sm:grid-cols-[1fr_7rem]">
              <input key={`r${shipping.quote.cep}`} name="street" required defaultValue={shipping.quote.street ?? ""} placeholder={`Rua (${shipping.quote.city}/${shipping.quote.uf})`} className={input} />
              <input name="number" required placeholder="Número" className={input} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <input name="complement" placeholder="Complemento" className={input} />
              <input key={`b${shipping.quote.cep}`} name="district" defaultValue={shipping.quote.district ?? ""} placeholder="Bairro" className={input} />
            </div>
            <div className="space-y-2">
              {shipping.quote.options.map((o) => (
                <label key={o.id} className={`flex cursor-pointer justify-between gap-3 rounded-xl border p-3 text-sm ${option === o.id ? "border-secondary bg-secondary/10" : "border-border"}`}>
                  <span className="flex gap-2">
                    <input type="radio" name="shipping_option" value={o.id} required onChange={() => setOption(o.id)} className="accent-[var(--secondary)]" />
                    <span>
                      {o.label}
                      {o.detail && <span className="block text-xs text-muted">{o.detail}</span>}
                    </span>
                  </span>
                  <span className="font-medium">{o.price === null ? "a calcular" : Number(o.price) === 0 ? "grátis" : money(o.price)}</span>
                </label>
              ))}
            </div>
          </>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-heading text-lg font-semibold">Pagamento</h2>
        <input type="hidden" name="payment_method" value={method} />
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => setMethod("pix")}
            aria-pressed={method === "pix"}
            className={`rounded-2xl border-2 p-4 text-left text-sm ${method === "pix" ? "border-secondary bg-secondary/10" : "border-border bg-surface"}`}
          >
            <span className="flex items-center justify-between font-bold">
              Pix <span className="seal">menor preço</span>
            </span>
            <span className="mt-1 block text-lg font-extrabold text-primary">{money(subtotalPix)}</span>
            <span className="text-xs text-muted">QR Code na próxima tela · confirmação na hora</span>
          </button>
          {subtotalCard && (
            <button
              type="button"
              onClick={() => setMethod("cartao")}
              aria-pressed={method === "cartao"}
              className={`rounded-2xl border-2 p-4 text-left text-sm ${method === "cartao" ? "border-secondary bg-secondary/10" : "border-border bg-surface"}`}
            >
              <span className="font-bold">Cartão de crédito</span>
              <span className="mt-1 block text-lg font-extrabold text-primary">{money(subtotalCard)}</span>
              <span className="text-xs text-muted">em até 12x · ambiente seguro do Mercado Pago</span>
            </button>
          )}
        </div>
        <p className="text-xs text-muted">Valores dos produtos; a entrega é somada conforme o CEP. A produção começa assim que o pagamento for aprovado.</p>
        <textarea name="notes" rows={2} placeholder="Observações (opcional)" className={input} />
      </section>

      <section className="space-y-2 text-sm">
        <label className="flex items-start gap-2">
          <input type="checkbox" name="accept_terms" required className="mt-1 accent-[var(--secondary)]" />
          Li e aceito os termos de compra e a política de privacidade. Peças personalizadas seguem política própria de troca.
        </label>
        <label className="flex items-start gap-2 text-muted">
          <input type="checkbox" name="marketing_opt_in" className="mt-1 accent-[var(--secondary)]" />
          Quero receber novidades e promoções (opcional)
        </label>
      </section>

      {state.error && <p className="rounded-xl bg-primary/10 p-3 text-sm text-primary">{state.error}</p>}
      <button disabled={pending || !shipping.quote} className="btn w-full text-lg">
        {pending ? "Enviando pedido…" : method === "cartao" ? "Fazer pedido e pagar com cartão" : "Fazer pedido e pagar com Pix"}
      </button>
      {!shipping.quote && (
        <p className="text-center text-sm text-muted">Informe o CEP em Entrega para calcular o frete e liberar o pagamento.</p>
      )}
    </form>
  );
}
