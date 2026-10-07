import Link from "next/link";
import { Badge, Card, PageHeader } from "@/components/ui";
import { api } from "@/lib/admin-api";
import { api as publicApi } from "@/lib/api";
import type { AuditEntry, Material, Printer } from "@/lib/types";

export const dynamic = "force-dynamic";

async function settled<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch {
    return null;
  }
}

export default async function Dashboard() {
  const [ready, materials, printers, fees, blocked] = await Promise.all([
    publicApi.getReadyOrNull(),
    settled(api.get<Material[]>("/materials")),
    settled(api.get<Printer[]>("/printers")),
    settled(api.get<{ channel: string }[]>("/channel-fees")),
    settled(api.get<AuditEntry[]>("/audit?decision=bloqueado&limit=5")),
  ]);
  const lowStock = materials?.filter((m) => m.active && m.low_stock) ?? [];
  const channels = new Set(fees?.map((f) => f.channel));
  const activePrinters = printers?.filter((p) => p.status === "ativa") ?? [];

  const stats = [
    { label: "Materiais", value: materials?.length ?? "—", href: "/materiais" },
    { label: "Impressoras ativas", value: activePrinters.length, href: "/impressoras" },
    { label: "Canais com tarifa", value: channels.size, href: "/tarifas" },
    { label: "Filamentos para repor", value: lowStock.length, href: "/materiais" },
  ];

  return (
    <>
      <PageHeader title="Visão geral" description="Estado do sistema e o que precisa da sua atenção." />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <Link key={s.label} href={s.href} className="rounded-2xl border border-border bg-surface p-5 hover:border-secondary">
            <p className="text-sm text-muted">{s.label}</p>
            <p className="mt-1 font-heading text-3xl font-bold">{s.value}</p>
          </Link>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Saúde do sistema">
          <ul className="space-y-2 text-sm">
            {Object.entries(ready?.checks ?? {}).map(([name, check]) => (
              <li key={name} className="flex justify-between">
                <span className="capitalize">{name}</span>
                {check.ok ? <Badge tone="ok">ok</Badge> : <Badge tone="danger">falha</Badge>}
              </li>
            ))}
            {!ready && <li className="text-muted">API indisponível.</li>}
          </ul>
        </Card>

        <Card title="Próximos passos">
          <ul className="list-inside list-disc space-y-1 text-sm text-muted">
            {activePrinters.length === 0 && (
              <li>
                Cadastre sua impressora em <Link className="text-secondary" href="/impressoras">Impressoras</Link> (pode ser “planejada”).
              </li>
            )}
            {(materials?.length ?? 0) === 0 && (
              <li>
                Cadastre os filamentos em <Link className="text-secondary" href="/materiais">Materiais</Link>.
              </li>
            )}
            {channels.size === 0 && (
              <li>
                Cadastre as tarifas dos canais em <Link className="text-secondary" href="/tarifas">Tarifas</Link> (conferindo a tabela oficial).
              </li>
            )}
            <li>
              Teste preços na <Link className="text-secondary" href="/calculadora">Calculadora</Link> e produtos no{" "}
              <Link className="text-secondary" href="/guardiao">Guardião</Link>.
            </li>
          </ul>
        </Card>

        {lowStock.length > 0 && (
          <Card title="Filamentos para repor">
            <ul className="space-y-2 text-sm">
              {lowStock.map((m) => (
                <li key={m.id} className="flex items-center gap-2">
                  <span className="size-4 rounded-full border border-border" style={{ background: m.color_hex }} />
                  {m.kind} {m.color_name} — {m.stock_grams} g
                </li>
              ))}
            </ul>
          </Card>
        )}

        <Card title="Últimos bloqueios do Guardião">
          {blocked && blocked.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {blocked.map((b) => (
                <li key={b.id}>
                  <span className="font-medium">{String((b.payload.entrada as { title?: string } | undefined)?.title ?? "—")}</span>
                  <span className="block text-xs text-muted">{b.reason}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">Nenhum bloqueio registrado.</p>
          )}
        </Card>
      </div>
    </>
  );
}
