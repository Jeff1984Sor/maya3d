import type { Metadata } from "next";
import Link from "next/link";
import { jobAction } from "@/actions/orders";
import { Flash } from "@/components/flash";
import { Badge, Card, Empty, PageHeader } from "@/components/ui";
import { api } from "@/lib/admin-api";
import type { QueueGroup } from "@/lib/types";

export const metadata: Metadata = { title: "Fila de impressão" };
export const dynamic = "force-dynamic";

export default async function FilaPage({ searchParams }: { searchParams: Promise<{ erro?: string }> }) {
  const groups = await api.get<QueueGroup[]>("/print-queue");
  return (
    <>
      <PageHeader
        title="Fila de impressão"
        description="Agrupada por material e cor para reduzir trocas de filamento; dentro do grupo, por prazo."
      />
      <Flash {...await searchParams} />
      {groups.length === 0 ? (
        <Empty>Fila vazia.</Empty>
      ) : (
        <div className="space-y-6">
          {groups.map((g) => (
            <Card key={g.material_key} title={`${g.materials.join(" + ")} — ${g.total_pieces} peça(s)`}>
              <ul className="divide-y divide-border">
                {g.jobs.map((j) => (
                  <li key={j.job_id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                    <Link href={`/pedidos/${j.order_id}`} className="font-medium hover:text-secondary">
                      #{j.order_number}
                    </Link>
                    <span>
                      {j.quantity}× {j.title}
                    </span>
                    {j.is_sample && <Badge tone="warn">amostra</Badge>}
                    {Object.keys(j.personalization).length > 0 && (
                      <span className="text-xs text-muted">{JSON.stringify(j.personalization)}</span>
                    )}
                    {j.due_date && <Badge>prazo {new Date(j.due_date).toLocaleDateString("pt-BR")}</Badge>}
                    <div className="ml-auto flex gap-2">
                      {j.status === "fila" ? (
                        <form action={jobAction.bind(null, j.job_id, "iniciar", "/fila")}>
                          <button className="rounded-lg bg-primary px-3 py-1.5 text-white">Iniciar</button>
                        </form>
                      ) : (
                        <Badge tone="ok">imprimindo</Badge>
                      )}
                      <form action={jobAction.bind(null, j.job_id, "concluir", "/fila")}>
                        <button className="rounded-lg border border-border px-3 py-1.5">Concluir</button>
                      </form>
                      <form action={jobAction.bind(null, j.job_id, "falhou", "/fila")}>
                        <button className="rounded-lg px-3 py-1.5 text-primary hover:bg-primary/10">Falhou</button>
                      </form>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
