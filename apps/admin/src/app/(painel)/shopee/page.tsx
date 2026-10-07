import type { Metadata } from "next";
import Link from "next/link";
import type { MlListing } from "@/actions/mercadolivre";
import { connectShopee, disconnectShopee, type ShopeeStatus } from "@/actions/shopee";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { Flash } from "@/components/flash";
import { SHOPEE_COLOR, ShopeeHero } from "@/components/shopee-brand";
import { Badge, Card, Empty } from "@/components/ui";
import { api } from "@/lib/admin-api";
import { formatMoney } from "@/lib/form";

export const metadata: Metadata = { title: "Shopee" };
export const dynamic = "force-dynamic";

function Step({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <span>{ok ? "✅" : "⬜"}</span>
      <span className={ok ? "text-muted" : ""}>{children}</span>
    </li>
  );
}

export default async function ShopeePage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const [status, listings] = await Promise.all([api.get<ShopeeStatus>("/shopee/status"), api.get<MlListing[]>("/shopee/listings")]);
  return (
    <>
      <ShopeeHero title="Shopee" subtitle="Loja conectada e anúncios. Pedidos pagos entram sozinhos na Produção.">
        <span className="rounded-full bg-white/20 px-4 py-1.5 text-sm font-semibold">
          {status.connected ? `● conectada · ${status.shop}` : "não conectada"}
        </span>
      </ShopeeHero>
      <Flash {...await searchParams} />

      <Card title="Conexão" className="mb-6">
        <ol className="mb-4 space-y-1 text-sm">
          <Step ok={status.https_ready}>
            Domínio com HTTPS e endereço público da API em <Link className="text-secondary hover:underline" href="/integracoes">Integrações</Link>
          </Step>
          <Step ok={status.configured}>
            App criado na Shopee Open Platform (Partner ID e Partner Key em Integrações). Push de pedidos em{" "}
            <code className="text-xs">https://api.&lt;domínio&gt;{status.webhook_path}</code>
          </Step>
          <Step ok={status.connected}>Loja autorizada {status.shop && <b>({status.shop})</b>}</Step>
        </ol>
        <div className="flex gap-2">
          <form action={connectShopee}>
            <button
              disabled={!status.configured || !status.https_ready}
              className="rounded-xl px-5 py-2.5 text-sm font-bold text-white shadow-sm transition hover:brightness-95 disabled:opacity-50"
              style={{ background: SHOPEE_COLOR }}
            >
              {status.connected ? "Reconectar" : "Conectar loja da Shopee"}
            </button>
          </form>
          {status.connected && (
            <form action={disconnectShopee}>
              <ConfirmSubmit message="Desconectar a loja? Os anúncios continuam na Shopee, mas os pedidos param de entrar." className="rounded-xl px-4 py-2 text-sm text-primary hover:bg-primary/10">
                Desconectar
              </ConfirmSubmit>
            </form>
          )}
        </div>
        <p className="mt-3 text-xs text-muted">
          A comissão da Shopee vem da tabela de Tarifas (canal <code>shopee</code>): o preço sugerido de cada variante já usa ela.
        </p>
      </Card>

      <Card title="Anúncios">
        {listings.length === 0 ? (
          <Empty>Nenhum anúncio. Anuncie pela página de cada produto.</Empty>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {listings.map((l) => (
                <tr key={l.id} className="border-t border-border">
                  <td className="py-2">
                    <Link href={`/produtos/${l.product_id}`} className="text-secondary hover:underline">
                      produto {l.product_id}
                    </Link>
                  </td>
                  <td>{formatMoney(l.price)}</td>
                  <td>
                    <Badge tone={l.status === "publicado" ? "ok" : l.status === "erro" ? "danger" : "muted"}>{l.status}</Badge>
                  </td>
                  <td className="max-w-xs truncate text-xs text-primary">{l.last_error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
