import type { Metadata } from "next";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { Flash } from "@/components/flash";
import { Alert, Badge, Button, Card, Empty, PageHeader } from "@/components/ui";
import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

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
  attempts: number;
  last_error: string | null;
  order_id: number | null;
};

type WaStatus = {
  configured: boolean;
  webhook_ready: boolean;
  template_fallback: boolean;
  graph_version: string | null;
  pending: number;
  failed: number;
};

const back = (key: "ok" | "erro", msg: string) => redirect(`/mensagens?${key}=${encodeURIComponent(msg)}`);
const errMsg = (error: unknown) => (error instanceof AdminApiError ? error.message : "Falha ao falar com a API.");

async function dispatchNow(): Promise<void> {
  "use server";
  await requireSession();
  let sent = 0;
  try {
    ({ sent } = await api.post<{ sent: number }>("/notifications/dispatch", {}));
  } catch (error) {
    back("erro", errMsg(error));
  }
  revalidatePath("/mensagens");
  back("ok", `${sent} mensagem(ns) enviada(s).`);
}

async function retry(id: number): Promise<void> {
  "use server";
  await requireSession();
  try {
    await api.post(`/notifications/${id}/retry`, {});
  } catch (error) {
    back("erro", errMsg(error));
  }
  revalidatePath("/mensagens");
  back("ok", "Mensagem volta para a fila de envio.");
}

const tone = (s: string) => (s === "enviado" ? "ok" : s === "falhou" ? "danger" : s === "pendente" ? "warn" : "muted");

export default async function MensagensPage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const [notes, wa] = await Promise.all([api.get<Note[]>("/notifications?limit=200"), api.get<WaStatus>("/whatsapp/status")]);
  return (
    <>
      <PageHeader
        title="Caixa de saída"
        description="Toda mensagem que o sistema gera (vendas, status, amostras, respostas aos seus comandos). Com o WhatsApp conectado, saem sozinhas em segundos."
      >
        {wa.configured && wa.pending > 0 && (
          <form action={dispatchNow}>
            <Button>Enviar pendentes agora</Button>
          </form>
        )}
      </PageHeader>
      <Flash {...await searchParams} />

      <Card title="WhatsApp (API oficial da Meta)" className="mb-6">
        <div className="flex flex-wrap gap-2 text-sm">
          <Badge tone={wa.configured ? "ok" : "warn"}>{wa.configured ? `envio ligado (${wa.graph_version})` : "envio desligado"}</Badge>
          <Badge tone={wa.webhook_ready ? "ok" : "warn"}>{wa.webhook_ready ? "webhook pronto" : "webhook sem segredo"}</Badge>
          <Badge tone={wa.template_fallback ? "ok" : "muted"}>
            {wa.template_fallback ? "template p/ fora das 24 h" : "sem template (só dentro das 24 h)"}
          </Badge>
          <Badge tone={wa.pending ? "warn" : "muted"}>{wa.pending} pendente(s)</Badge>
          <Badge tone={wa.failed ? "danger" : "muted"}>{wa.failed} falha(s)</Badge>
        </div>
        {!wa.configured && (
          <p className="mt-3 text-sm text-muted">
            Para ligar: preencha WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID e WHATSAPP_GRAPH_VERSION no .env do servidor e reinicie. Nada se perde
            enquanto isso: as mensagens ficam aqui, pendentes.
          </p>
        )}
        {wa.configured && !wa.webhook_ready && (
          <p className="mt-3 text-sm text-muted">
            Para receber respostas (botão Aprovar, seus comandos): WHATSAPP_APP_SECRET e WHATSAPP_VERIFY_TOKEN, e registrar o webhook
            /v1/webhooks/whatsapp na Meta (precisa de domínio com HTTPS).
          </p>
        )}
      </Card>

      {wa.failed > 0 && <Alert tone="error">{wa.failed} mensagem(ns) falharam depois de 5 tentativas. Veja o erro e tente de novo.</Alert>}
      {notes.length === 0 ? (
        <Empty>Nenhuma mensagem gerada ainda.</Empty>
      ) : (
        <ul className="space-y-3">
          {notes.map((n) => (
            <li key={n.id} className="rounded-xl border border-border bg-surface p-4 text-sm">
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                <Badge tone={tone(n.status)}>{n.status}</Badge>
                <span>{n.audience === "dono" ? "para você" : "para o cliente"}</span>
                <span>{n.to ?? n.last_error}</span>
                <span className="ml-auto">{new Date(n.created_at).toLocaleString("pt-BR")}</span>
              </div>
              <p className="whitespace-pre-line">{n.body}</p>
              {n.status === "falhou" && (
                <form action={retry.bind(null, n.id)} className="mt-2 flex items-center gap-3">
                  <span className="text-xs text-primary">{n.last_error}</span>
                  <Button variant="secondary" className="ml-auto">
                    Tentar de novo
                  </Button>
                </form>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
