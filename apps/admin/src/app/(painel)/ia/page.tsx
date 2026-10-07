import type { Metadata } from "next";
import { saveAiConfig } from "@/actions/ai";
import { Flash } from "@/components/flash";
import { Alert, Badge, Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/admin-api";

export const metadata: Metadata = { title: "IA" };
export const dynamic = "force-dynamic";

type Status = {
  configured: boolean;
  provider: string;
  models: Record<string, string | null>;
  available_models: string[];
  error: string | null;
};

const TASKS = [
  { key: "default", label: "Tarefas do dia a dia", hint: "✨ Enriquecer, Redator, sugestões" },
  { key: "guardian", label: "Guardião visual", hint: "análise de imagens; use um modelo forte" },
  { key: "personalizer", label: "Personalizador", hint: "pedido em linguagem natural → parâmetros" },
  { key: "embedding", label: "Busca semântica (embeddings)", hint: "Fase 6" },
];

export default async function IaPage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const status = await api.get<Status>("/ai/status");
  return (
    <>
      <PageHeader
        title="Inteligência artificial"
        description="A chave e o fornecedor ficam no servidor (.env). Aqui você escolhe qual modelo da sua conta faz cada tarefa."
      />
      <Flash {...await searchParams} />
      <div className="mb-6 flex flex-wrap gap-2">
        <Badge tone={status.configured ? "ok" : "danger"}>{status.configured ? "chave configurada" : "sem chave"}</Badge>
        <Badge>fornecedor: {status.provider}</Badge>
      </div>
      {status.error && <Alert tone="error">{status.error}</Alert>}
      <Card title="Modelos por tarefa">
        <form action={saveAiConfig} className="grid gap-4 sm:grid-cols-2">
          {TASKS.map((t) => (
            <Label key={t.key} label={t.label} hint={t.hint}>
              <select name={`model_${t.key}`} defaultValue={status.models[t.key] ?? ""} className={inputClass}>
                <option value="">— escolher —</option>
                {status.models[t.key] && !status.available_models.includes(status.models[t.key]!) && (
                  <option value={status.models[t.key]!}>{status.models[t.key]}</option>
                )}
                {status.available_models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </Label>
          ))}
          <Label label="Limite diário de gasto (US$)">
            <input name="daily_budget_usd" defaultValue="5" inputMode="decimal" className={inputClass} />
          </Label>
          <div className="sm:col-span-2">
            <Button type="submit" disabled={!status.configured}>
              Salvar
            </Button>
          </div>
        </form>
      </Card>
    </>
  );
}
