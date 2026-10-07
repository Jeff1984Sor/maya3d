import type { Metadata } from "next";
import { Alert, Badge, Empty, PageHeader } from "@/components/ui";
import { api } from "@/lib/admin-api";

export const metadata: Metadata = { title: "Caixa de saída" };
export const dynamic = "force-dynamic";

type Note = {
  id: number;
  created_at: string;
  channel: string;
  audience: string;
  to: string | null;
  template: string;
  body: string;
  status: string;
  last_error: string | null;
  order_id: number | null;
};

export default async function MensagensPage() {
  const notes = await api.get<Note[]>("/notifications?limit=200");
  const pending = notes.filter((n) => n.status === "pendente").length;
  return (
    <>
      <PageHeader
        title="Caixa de saída"
        description="Toda mensagem que o sistema gera (vendas, status, amostras). Quando o WhatsApp Business for conectado, as pendentes são enviadas automaticamente."
      />
      {pending > 0 && (
        <Alert tone="error">
          {pending} mensagem(ns) aguardando o WhatsApp ser conectado. Nada se perde: elas saem quando a conta Meta for configurada.
        </Alert>
      )}
      {notes.length === 0 ? (
        <Empty>Nenhuma mensagem gerada ainda.</Empty>
      ) : (
        <ul className="space-y-3">
          {notes.map((n) => (
            <li key={n.id} className="rounded-xl border border-border bg-surface p-4 text-sm">
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                <Badge tone={n.status === "enviado" ? "ok" : n.status === "falhou" ? "danger" : n.status === "pendente" ? "warn" : "muted"}>
                  {n.status}
                </Badge>
                <span>{n.audience === "dono" ? "para você" : "para o cliente"}</span>
                <span>{n.to ?? n.last_error}</span>
                <span className="ml-auto">{new Date(n.created_at).toLocaleString("pt-BR")}</span>
              </div>
              <p>{n.body}</p>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
