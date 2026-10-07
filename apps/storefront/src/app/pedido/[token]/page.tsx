import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Container } from "@/components/shop";
import { money } from "@/lib/format";
import { StoreApiError, storeApi, type PublicOrder } from "@/lib/store";
import { CopyButton } from "./copy-button";

export const metadata: Metadata = { title: "Meu pedido", robots: { index: false } };
export const dynamic = "force-dynamic";

export default async function PedidoPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  if (!/^[A-Za-z0-9_-]{10,60}$/.test(token)) notFound();
  let order: PublicOrder;
  try {
    order = await storeApi<PublicOrder>(`/orders/${token}`);
  } catch (error) {
    if (error instanceof StoreApiError && error.status === 404) notFound();
    throw error;
  }

  return (
    <Container className="max-w-3xl py-10">
      <p className="text-sm text-muted">Pedido #{order.number}</p>
      <h1 className="font-heading text-3xl font-bold">{order.status_label}</h1>
      {order.progress && <p className="mt-1 text-muted">{order.progress}</p>}

      {order.pix && (
        <section className="mt-8 rounded-2xl border-2 border-secondary bg-secondary/5 p-6">
          <h2 className="font-heading text-xl font-semibold">Pague com Pix</h2>
          <p className="mt-1 text-sm text-muted">Valor: <strong className="text-ink">{money(order.pix.amount)}</strong></p>
          {order.pix.key ? (
            <div className="mt-4 space-y-2">
              <p className="text-sm">Chave Pix{order.pix.name ? ` (${order.pix.name})` : ""}:</p>
              <div className="flex flex-wrap items-center gap-2">
                <code className="rounded-lg bg-surface px-3 py-2 text-sm">{order.pix.key}</code>
                <CopyButton text={order.pix.key} />
              </div>
              <p className="text-xs text-muted">Assim que o pagamento cair, você recebe a confirmação e a produção começa.</p>
            </div>
          ) : (
            <p className="mt-3 text-sm">Em instantes enviamos a chave Pix pelo WhatsApp.</p>
          )}
        </section>
      )}

      <section className="mt-8">
        <h2 className="mb-3 font-heading text-lg font-semibold">Andamento</h2>
        <ol className="space-y-4 border-l-2 border-border pl-5">
          {order.timeline.map((t, i) => (
            <li key={i} className="relative">
              <span className="absolute -left-[27px] top-1 size-3 rounded-full bg-secondary" />
              <p className="font-medium">{t.label}</p>
              <p className="text-xs text-muted">{new Date(t.at).toLocaleString("pt-BR")}</p>
              {t.media_url && (
                <a href={t.media_url} target="_blank" rel="noreferrer" className="text-xs text-secondary">
                  ver foto/vídeo
                </a>
              )}
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-8 rounded-2xl border border-border bg-surface p-5 text-sm">
        <ul className="space-y-1">
          {order.items.map((i, n) => (
            <li key={n}>
              {i.quantity}× {i.title}
              {Object.values(i.personalization).filter(Boolean).length > 0 && (
                <span className="text-muted"> · {Object.values(i.personalization).filter(Boolean).join(", ")}</span>
              )}
            </li>
          ))}
        </ul>
        <p className="mt-3 flex justify-between border-t border-border pt-3 font-semibold">
          <span>Total</span>
          <span>{money(order.total)}</span>
        </p>
      </section>
      <p className="mt-6 text-center text-xs text-muted">Guarde este link: é por ele que você acompanha o pedido.</p>
    </Container>
  );
}
