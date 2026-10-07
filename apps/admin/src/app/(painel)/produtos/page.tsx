import type { Metadata } from "next";
import Link from "next/link";
import { Flash } from "@/components/flash";
import { GuardianBadge, StatusBadge } from "@/components/product-badges";
import { Empty, PageHeader, cx } from "@/components/ui";
import { api } from "@/lib/admin-api";
import type { ProductSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Produtos" };
export const dynamic = "force-dynamic";

const FILTERS = [
  { label: "Todos", value: "" },
  { label: "Aprovados", value: "aprovado" },
  { label: "Bloqueados", value: "bloqueado" },
];

export default async function ProdutosPage({
  searchParams,
}: {
  searchParams: Promise<{ guardiao?: string; ok?: string; erro?: string }>;
}) {
  const { guardiao = "", ...flash } = await searchParams;
  const products = await api.get<ProductSummary[]>(`/products${guardiao ? `?guardiao=${guardiao}` : ""}`);

  return (
    <>
      <PageHeader
        title="Produtos"
        description="Cada produto passa pelo Guardião ao ser salvo. Bloqueado não ativa; sem impressora capaz do material mínimo, fica aguardando equipamento."
      >
        <Link href="/produtos/novo" className="rounded-xl bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90">
          Novo produto
        </Link>
      </PageHeader>
      <Flash {...flash} />
      <nav className="mb-4 flex gap-2 text-sm">
        {FILTERS.map((f) => (
          <Link
            key={f.label}
            href={f.value ? `/produtos?guardiao=${f.value}` : "/produtos"}
            className={cx(
              "rounded-full border px-3 py-1",
              guardiao === f.value ? "border-secondary bg-secondary/10" : "border-border hover:bg-surface",
            )}
          >
            {f.label}
          </Link>
        ))}
      </nav>
      {products.length === 0 ? (
        <Empty>Nenhum produto ainda.</Empty>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">Produto</th>
                <th className="px-4 py-3">Nicho</th>
                <th className="px-4 py-3">Variantes</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Guardião</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} className="border-b border-border last:border-0 hover:bg-bg/60">
                  <td className="px-4 py-3">
                    <Link href={`/produtos/${p.id}`} className="font-medium hover:text-secondary">
                      {p.title}
                    </Link>
                    <span className="block text-xs text-muted">{p.category}</span>
                  </td>
                  <td className="px-4 py-3">{p.niche}</td>
                  <td className="px-4 py-3">{p.variant_count}</td>
                  <td className="px-4 py-3">
                    <StatusBadge product={p} />
                  </td>
                  <td className="px-4 py-3">
                    <GuardianBadge status={p.guardian_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
