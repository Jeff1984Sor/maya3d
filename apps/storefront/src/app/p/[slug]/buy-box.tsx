"use client";

import { useActionState, useState } from "react";
import { addToCart, type AddState } from "@/actions/cart";
import { money } from "@/lib/format";
import type { Product } from "@/lib/store";

/** Escolha de variante, cor, quantidade e texto; preço muda ao vivo. */
export function BuyBox({ product, personalization = {} }: { product: Product; personalization?: Record<string, string> }) {
  const [state, action, pending] = useActionState<AddState, FormData>(addToCart, {});
  const sellable = product.variants.filter((v) => v.price_pix);
  const [variantId, setVariantId] = useState(sellable[0]?.id ?? product.variants[0]?.id);
  const variant = product.variants.find((v) => v.id === variantId) ?? product.variants[0];
  const [colorId, setColorId] = useState<number | undefined>(variant?.colors[0]?.material_id);
  const [qty, setQty] = useState(1);

  if (!variant || !variant.price_pix) {
    return (
      <p className="rounded-2xl border border-dashed border-border p-4 text-muted">
        Produto sem preço no momento. Fale com a gente pelo WhatsApp para um orçamento.
      </p>
    );
  }

  return (
    <form action={action} className="space-y-5">
      <input type="hidden" name="variant_id" value={variant.id} />
      <input type="hidden" name="material_id" value={colorId ?? ""} />
      {Object.entries(personalization).map(([k, v]) => (
        <input key={k} type="hidden" name={`p_${k}`} value={v} />
      ))}

      <div>
        <p className="font-heading text-3xl font-bold text-primary">{money(Number(variant.price_pix) * qty)}</p>
        <p className="text-sm text-muted">no Pix · {money(Number(variant.price_card ?? variant.price_pix) * qty)} no cartão</p>
      </div>

      {product.variants.length > 1 && (
        <div>
          <p className="mb-2 text-sm font-medium">Opção</p>
          <div className="flex flex-wrap gap-2">
            {product.variants.map((v) => (
              <button
                key={v.id}
                type="button"
                disabled={!v.price_pix}
                onClick={() => {
                  setVariantId(v.id);
                  setColorId(v.colors[0]?.material_id);
                }}
                className={`rounded-xl border px-4 py-2 text-sm disabled:opacity-40 ${v.id === variant.id ? "border-ink bg-ink text-bg" : "border-border"}`}
              >
                {v.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {variant.colors.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-medium">
            Cor: <span className="text-muted">{variant.colors.find((c) => c.material_id === colorId)?.name}</span>
          </p>
          <div className="flex flex-wrap gap-2">
            {variant.colors.map((c) => (
              <button
                key={c.material_id}
                type="button"
                title={c.name}
                onClick={() => setColorId(c.material_id)}
                className={`size-9 rounded-full border-2 ${c.material_id === colorId ? "border-primary ring-2 ring-primary/30" : "border-border"}`}
                style={{ background: c.hex }}
              />
            ))}
          </div>
        </div>
      )}

      {product.customizable && Object.keys(personalization).length === 0 && (
        <label className="block text-sm">
          <span className="font-medium">Personalização (nome, frase…)</span>
          <input name="p_texto" maxLength={60} className="mt-1 w-full rounded-xl border border-border bg-surface px-3 py-2" />
        </label>
      )}

      <div className="flex items-center gap-3">
        <div className="flex items-center rounded-xl border border-border">
          <button type="button" className="px-3 py-2" onClick={() => setQty(Math.max(1, qty - 1))}>
            −
          </button>
          <input name="quantity" value={qty} readOnly className="w-10 bg-transparent text-center" />
          <button type="button" className="px-3 py-2" onClick={() => setQty(Math.min(999, qty + 1))}>
            +
          </button>
        </div>
        <button disabled={pending} className="flex-1 rounded-xl bg-primary px-6 py-3 font-semibold text-white hover:opacity-90 disabled:opacity-50">
          {pending ? "Adicionando…" : "Adicionar ao carrinho"}
        </button>
      </div>
      {qty > 10 && <p className="text-xs text-muted">Pedidos acima de 10 unidades passam por aprovação de amostra antes da produção.</p>}
      {state.error && <p className="rounded-xl bg-primary/10 p-3 text-sm text-primary">{state.error}</p>}
    </form>
  );
}
