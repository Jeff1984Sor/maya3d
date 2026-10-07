import type { Metadata } from "next";
import Link from "next/link";
import { advanceOrder } from "@/actions/orders";
import { Flash } from "@/components/flash";
import { Badge, Empty, PageHeader } from "@/components/ui";
import { api } from "@/lib/admin-api";
import { ACTIVE_STATUSES, label, statusTone } from "@/lib/order-labels";
import type { OrderSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Produção" };
export const dynamic = "force-dynamic";

/** Tela pensada para o celular: um card por pedido, botão grande para o próximo passo. */
export default async function ProducaoPage({ searchParams }: { searchParams: Promise<{ erro?: string }> }) {
  const orders = (await api.get<OrderSummary[]>("/orders")).filter((o) => ACTIVE_STATUSES.includes(o.status));

  return (
    <>
      <PageHeader title="Produção" description="Cada toque grava o status com data/hora e avisa o cliente (site/app) na hora." />
      <Flash {...await searchParams} />
      {orders.length === 0 ? (
        <Empty>Nada em produção agora.</Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {orders.map((o) => (
            <article key={o.id} className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-5">
              <div className="flex items-center justify-between">
                <Link href={`/pedidos/${o.id}`} className="font-heading text-xl font-bold hover:text-secondary">
                  #{o.number}
                </Link>
                <Badge tone={statusTone(o.status)}>{label(o.status)}</Badge>
              </div>
              <p className="text-sm text-muted">
                {o.channel} · {o.progress || "sem itens"}
                {o.promised_date && ` · prazo ${new Date(o.promised_date).toLocaleDateString("pt-BR")}`}
              </p>
              {o.status === "amostra_pronta" ? (
                <Link
                  href={`/pedidos/${o.id}`}
                  className="rounded-xl border border-secondary px-4 py-4 text-center font-medium text-secondary"
                >
                  Aguardando o cliente aprovar a amostra
                </Link>
              ) : o.next_step ? (
                <form action={advanceOrder.bind(null, o.id, o.next_step, "/producao")}>
                  <button type="submit" className="w-full rounded-xl bg-primary px-4 py-4 text-lg font-semibold text-white active:scale-[0.99]">
                    {o.status === "aguardando_pagamento" ? "Pix recebido — iniciar produção" : `${label(o.next_step)} →`}
                  </button>
                </form>
              ) : null}
              {o.status === "embalado" && o.local_delivery && (
                <form action={advanceOrder.bind(null, o.id, "saiu_para_entrega", "/producao")}>
                  <button type="submit" className="w-full rounded-xl border border-border px-4 py-3 font-medium">
                    Saiu para entrega local
                  </button>
                </form>
              )}
            </article>
          ))}
        </div>
      )}
    </>
  );
}
