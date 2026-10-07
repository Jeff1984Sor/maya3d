"use client";

import { useActionState } from "react";
import { quoteShipping, type ShippingState } from "@/actions/cart";
import { money } from "@/lib/format";

/** CEP → opções de entrega; em Sorocaba mostra quanto falta para o frete grátis (spec 2.9). */
export function ShippingCalc() {
  const [state, action, pending] = useActionState<ShippingState, FormData>(quoteShipping, {});
  const quote = state.quote;
  const missing = quote?.missing_for_free ? Number(quote.missing_for_free) : 0;
  const min = quote?.free_shipping_min ? Number(quote.free_shipping_min) : 0;

  return (
    <div className="mt-4 space-y-3 border-t border-border pt-4">
      <form action={action} className="flex gap-2">
        <input name="cep" placeholder="Seu CEP" inputMode="numeric" maxLength={9} className="w-full rounded-xl border border-border bg-bg px-3 py-2 text-sm" />
        <button disabled={pending} className="rounded-xl border border-border px-4 text-sm">
          {pending ? "…" : "Calcular"}
        </button>
      </form>
      {state.error && <p className="text-sm text-primary">{state.error}</p>}
      {quote && (
        <div className="space-y-2 text-sm">
          <p className="text-muted">
            {quote.city}/{quote.uf}
          </p>
          {quote.local && min > 0 && (
            <div>
              {missing > 0 ? (
                <p>
                  Faltam <strong className="text-primary">{money(missing)}</strong> para a entrega grátis
                </p>
              ) : (
                <p className="font-medium text-secondary">Você ganhou entrega grátis! 🎉</p>
              )}
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-border">
                <div className="h-full bg-secondary transition-all" style={{ width: `${Math.min(100, ((min - missing) / min) * 100)}%` }} />
              </div>
            </div>
          )}
          <ul className="space-y-1">
            {quote.options.map((o) => (
              <li key={o.id} className="flex justify-between gap-2">
                <span>
                  {o.label}
                  {o.detail && <span className="block text-xs text-muted">{o.detail}</span>}
                </span>
                <span className="whitespace-nowrap font-medium">
                  {o.price === null ? "a calcular" : Number(o.price) === 0 ? "grátis" : money(o.price)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
