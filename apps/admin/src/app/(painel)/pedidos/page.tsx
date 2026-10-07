import type { Metadata } from "next";
import Link from "next/link";
import { createManualOrder } from "@/actions/orders";
import { Flash } from "@/components/flash";
import { Badge, Button, Card, Empty, Label, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/admin-api";
import { formatMoney } from "@/lib/form";
import { label, statusTone } from "@/lib/order-labels";
import type { Material, OrderSummary, ProductDetail, ProductSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Pedidos" };
export const dynamic = "force-dynamic";

type Customer = { id: number; name: string };

export default async function PedidosPage({ searchParams }: { searchParams: Promise<{ erro?: string }> }) {
  const [orders, customers, materials, products] = await Promise.all([
    api.get<OrderSummary[]>("/orders"),
    api.get<Customer[]>("/customers"),
    api.get<Material[]>("/materials"),
    api.get<ProductSummary[]>("/products"),
  ]);
  const details = await Promise.all(products.slice(0, 50).map((p) => api.get<ProductDetail>(`/products/${p.id}`)));
  const variants = details.flatMap((p) => p.variants.map((v) => ({ id: v.id, label: `${p.title} · ${v.sku}` })));

  return (
    <>
      <PageHeader title="Pedidos" description="Todos os canais num lugar só. Mercado Livre e Shopee entram pelas integrações." />
      <Flash {...await searchParams} />
      {orders.length === 0 ? (
        <Empty>Nenhum pedido ainda.</Empty>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">Pedido</th>
                <th className="px-4 py-3">Canal</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Produção</th>
                <th className="px-4 py-3 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} className="border-b border-border last:border-0 hover:bg-bg/60">
                  <td className="px-4 py-3">
                    <Link href={`/pedidos/${o.id}`} className="font-medium hover:text-secondary">
                      #{o.number}
                    </Link>
                    <span className="block text-xs text-muted">{new Date(o.created_at).toLocaleString("pt-BR")}</span>
                  </td>
                  <td className="px-4 py-3">{o.channel}</td>
                  <td className="px-4 py-3">
                    <Badge tone={statusTone(o.status)}>{label(o.status)}</Badge>
                  </td>
                  <td className="px-4 py-3 text-muted">{o.progress}</td>
                  <td className="px-4 py-3 text-right">{formatMoney(o.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Card title="Lançar venda manual (balcão, B2B ou teste)" className="mt-8">
        <form action={createManualOrder} className="grid gap-4 sm:grid-cols-3">
          <Label label="Canal">
            <select name="channel" className={inputClass} defaultValue="manual">
              <option value="manual">manual</option>
              <option value="site">site</option>
            </select>
          </Label>
          <Label label="Cliente">
            <select name="customer_id" className={inputClass} defaultValue="">
              <option value="">—</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Label>
          <Label label="Prazo prometido">
            <input type="date" name="promised_date" className={inputClass} />
          </Label>
          <Label label="Variante" hint="ou descreva no título">
            <select name="variant_id" className={inputClass} defaultValue="">
              <option value="">—</option>
              {variants.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label}
                </option>
              ))}
            </select>
          </Label>
          <Label label="Título (se não houver variante)">
            <input name="title" className={inputClass} />
          </Label>
          <Label label="Material/cor">
            <select name="material_id" className={inputClass} defaultValue="">
              <option value="">—</option>
              {materials.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.kind} {m.color_name}
                </option>
              ))}
            </select>
          </Label>
          <Label label="Quantidade *" hint="acima do limite: passa por amostra">
            <input name="quantity" type="number" min={1} required defaultValue={1} className={inputClass} />
          </Label>
          <Label label="Preço unitário (R$) *">
            <input name="unit_price" required inputMode="decimal" className={inputClass} />
          </Label>
          <Label label="Personalização" hint="ex.: nome Ana">
            <input name="personalization" className={inputClass} />
          </Label>
          <div className="sm:col-span-3">
            <Button type="submit">Lançar pedido</Button>
          </div>
        </form>
      </Card>
    </>
  );
}
