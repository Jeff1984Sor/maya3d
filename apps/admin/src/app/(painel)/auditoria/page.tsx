import type { Metadata } from "next";
import Link from "next/link";
import { Badge, Empty, PageHeader, cx } from "@/components/ui";
import { api } from "@/lib/admin-api";
import type { AuditEntry } from "@/lib/types";

export const metadata: Metadata = { title: "Auditoria" };
export const dynamic = "force-dynamic";

const FILTERS = [
  { label: "Tudo", value: "" },
  { label: "Bloqueados", value: "bloqueado" },
  { label: "Aprovados", value: "aprovado" },
];

export default async function AuditoriaPage({ searchParams }: { searchParams: Promise<{ decision?: string }> }) {
  const { decision = "" } = await searchParams;
  const qs = new URLSearchParams({ limit: "200", ...(decision ? { decision } : {}) });
  const entries = await api.get<AuditEntry[]>(`/audit?${qs}`);

  return (
    <>
      <PageHeader
        title="Auditoria"
        description="Toda decisão automática e alteração de custos, com motivo. Só consulta: nada aqui é aprovação manual."
      />
      <nav className="mb-4 flex gap-2 text-sm">
        {FILTERS.map((f) => (
          <Link
            key={f.label}
            href={f.value ? `/auditoria?decision=${f.value}` : "/auditoria"}
            className={cx(
              "rounded-full border px-3 py-1",
              decision === f.value ? "border-secondary bg-secondary/10" : "border-border hover:bg-surface",
            )}
          >
            {f.label}
          </Link>
        ))}
      </nav>
      {entries.length === 0 ? (
        <Empty>Nada registrado ainda.</Empty>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">Quando</th>
                <th className="px-4 py-3">Quem</th>
                <th className="px-4 py-3">O quê</th>
                <th className="px-4 py-3">Decisão</th>
                <th className="px-4 py-3">Motivo</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => {
                const title = (e.payload.entrada as { title?: string } | undefined)?.title;
                return (
                  <tr key={e.id} className="border-b border-border align-top last:border-0">
                    <td className="whitespace-nowrap px-4 py-3 text-muted">{new Date(e.created_at).toLocaleString("pt-BR")}</td>
                    <td className="px-4 py-3">{e.actor}</td>
                    <td className="px-4 py-3">
                      {e.action}
                      {title && <span className="block text-xs text-muted">{title}</span>}
                    </td>
                    <td className="px-4 py-3">
                      {e.decision === "bloqueado" ? (
                        <Badge tone="danger">bloqueado</Badge>
                      ) : e.decision ? (
                        <Badge tone="ok">{e.decision}</Badge>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted">{e.reason ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
