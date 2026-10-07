import Link from "next/link";
import { notFound } from "next/navigation";
import { advanceOrder } from "@/actions/orders";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { Flash } from "@/components/flash";
import { Badge, Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { AdminApiError, api } from "@/lib/admin-api";
import { formatMoney } from "@/lib/form";
import { label, statusTone } from "@/lib/order-labels";
import type { OrderDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function PedidoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ erro?: string }>;
}) {
  const id = Number((await params).id);
  if (!Number.isInteger(id)) notFound();
  let order: OrderDetail;
  try {
    order = await api.get<OrderDetail>(`/orders/${id}`);
  } catch (error) {
    if (error instanceof AdminApiError && error.status === 404) notFound();
    throw error;
  }
  const back = `/pedidos/${id}`;
  const actions = order.allowed.filter((s) => s !== "cancelado");

  return (
    <>
      <PageHeader title={`Pedido #${order.number}`} description={`${order.channel} · ${new Date(order.created_at).toLocaleString("pt-BR")}`}>
        <Link href="/pedidos" className="text-sm text-secondary hover:underline">
          ← pedidos
        </Link>
      </PageHeader>
      <Flash {...await searchParams} />

      <div className="mb-6 flex flex-wrap items-center gap-2">
        <Badge tone={statusTone(order.status)}>{label(order.status)}</Badge>
        {order.progress && <Badge>{order.progress}</Badge>}
        {order.sample_rounds > 0 && <Badge tone="warn">{order.sample_rounds} rodada(s) de ajuste</Badge>}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="space-y-6">
          {actions.length > 0 && (
            <Card title="Próximo passo">
              <form className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Label label="Observação" hint="vai para a linha do tempo">
                    <input name="note" className={inputClass} />
                  </Label>
                  <Label label="Foto/vídeo (link)" hint="ex.: foto da amostra">
                    <input name="media_url" className={inputClass} />
                  </Label>
                </div>
                <div className="flex flex-wrap gap-2">
                  {actions.map((to) => (
                    <Button key={to} formAction={advanceOrder.bind(null, id, to, back)} variant={to === order.next_step ? "primary" : "secondary"}>
                      {to === "na_fila" && order.status === "amostra_pronta"
                        ? "Cliente aprovou a amostra"
                        : to === "pago" && order.status === "aguardando_pagamento"
                          ? "Pix recebido — iniciar produção"
                          : label(to)}
                    </Button>
                  ))}
                </div>
              </form>
            </Card>
          )}

          <Card title="Itens">
            <table className="w-full text-sm">
              <tbody>
                {order.items.map((i) => (
                  <tr key={i.id} className="border-b border-border last:border-0">
                    <td className="py-2">
                      {i.quantity}× {i.title}
                      {Object.keys(i.personalization).length > 0 && (
                        <span className="block text-xs text-muted">{JSON.stringify(i.personalization)}</span>
                      )}
                    </td>
                    <td className="py-2 text-right text-muted">
                      {i.produced}/{i.quantity} {i.needs_sample && <Badge tone="warn">amostra</Badge>}
                    </td>
                    <td className="py-2 text-right">{formatMoney(Number(i.unit_price) * i.quantity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-right font-semibold">Total {formatMoney(order.total)}</p>
          </Card>

          <Card title="Impressões">
            <ul className="space-y-1 text-sm">
              {order.jobs.map((j) => (
                <li key={j.id} className="flex justify-between">
                  <span>
                    #{j.id} · {j.quantity} un. {j.is_sample && <Badge tone="warn">amostra</Badge>}
                  </span>
                  <span className="text-muted">
                    {j.status}
                    {j.failure_reason && ` (${j.failure_reason})`}
                  </span>
                </li>
              ))}
            </ul>
            <Link href="/fila" className="mt-3 inline-block text-sm text-secondary hover:underline">
              abrir fila de impressão →
            </Link>
          </Card>
        </div>

        <aside className="space-y-6">
          <Card title="Linha do tempo">
            <ol className="space-y-3 border-l border-border pl-4 text-sm">
              {order.events.map((e, n) => (
                <li key={n}>
                  <p className="font-medium">{label(e.status)}</p>
                  <p className="text-xs text-muted">
                    {new Date(e.created_at).toLocaleString("pt-BR")} · {e.actor}
                  </p>
                  {e.note && <p className="text-xs">{e.note}</p>}
                  {e.media_url && (
                    <a href={e.media_url} target="_blank" rel="noreferrer" className="text-xs text-secondary">
                      ver mídia
                    </a>
                  )}
                </li>
              ))}
            </ol>
          </Card>
          {order.customer && (
            <Card title="Cliente">
              <p className="text-sm">{order.customer.name}</p>
              <p className="text-xs text-muted">{order.customer.whatsapp ?? "sem WhatsApp"}</p>
            </Card>
          )}
          {order.allowed.includes("cancelado") && (
            <form action={advanceOrder.bind(null, id, "cancelado", back)}>
              <ConfirmSubmit message="Cancelar o pedido? As impressões na fila serão canceladas." className="text-sm text-primary hover:underline">
                Cancelar pedido
              </ConfirmSubmit>
            </form>
          )}
        </aside>
      </div>
    </>
  );
}
