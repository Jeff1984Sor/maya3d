import type { Metadata } from "next";
import { reindexSearch, saveAiConfig } from "@/actions/ai";
import { Flash } from "@/components/flash";
import { Alert, Badge, Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { AdminApiError, api } from "@/lib/admin-api";

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
  { key: "guardian", label: "Guardião visual", hint: "olha as fotos dos produtos (personagens, marcas); precisa enxergar imagens" },
  { key: "personalizer", label: "Personalizador e assistente da loja", hint: "conversa com o cliente; vazio = usa o do dia a dia" },
  { key: "embedding", label: "Busca semântica (embeddings)", hint: "busca por significado na loja e no assistente (OpenAI)" },
];

type SearchStatus = { enabled: boolean; model: string | null; products: number; indexed: number };
type SearchTest = { max_distance: number; hits: { product_id: number; title: string; distance: number; shown: boolean }[] };

export default async function IaPage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string; q?: string }> }) {
  const params = await searchParams;
  const [status, search] = await Promise.all([api.get<Status>("/ai/status"), api.get<SearchStatus>("/ai/search/status")]);
  let test: SearchTest | null = null;
  let testError: string | null = null;
  if (params.q && search.enabled) {
    try {
      test = await api.get<SearchTest>(`/ai/search/test?q=${encodeURIComponent(params.q)}`);
    } catch (error) {
      testError = error instanceof AdminApiError ? error.message : "Falha ao testar a busca.";
    }
  }
  return (
    <>
      <PageHeader
        title="Inteligência artificial"
        description="A chave fica em Integrações. Aqui você escolhe qual modelo da sua conta faz cada tarefa."
      />
      <Flash ok={params.ok} erro={params.erro} />
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

      <Card title="🔎 Busca por significado" className="mt-6">
        {!search.enabled ? (
          <p className="text-sm text-muted">
            Desligada: escolha o modelo de embedding acima (precisa de chave OpenAI; se a IA principal for Claude, cole uma chave OpenAI em
            Integrações → busca por significado). Enquanto isso a loja busca por palavras.
          </p>
        ) : (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
              <Badge tone={search.indexed === search.products ? "ok" : "warn"}>
                {search.indexed} de {search.products} produtos indexados
              </Badge>
              <Badge>{search.model}</Badge>
              <form action={reindexSearch} className="ml-auto">
                <Button variant="secondary">Indexar agora</Button>
              </form>
            </div>
            <p className="mb-3 text-xs text-muted">Produto novo ou editado entra na busca sozinho em até 5 minutos.</p>
            <form className="flex gap-2">
              <input name="q" defaultValue={params.q ?? ""} placeholder="ex.: presente para madrinha de batismo" className={inputClass} />
              <Button type="submit">Testar</Button>
            </form>
            {testError && <Alert tone="error">{testError}</Alert>}
            {test && (
              <ul className="mt-4 space-y-1 text-sm">
                {test.hits.length === 0 && <li className="text-muted">Nada parecido no catálogo à venda.</li>}
                {test.hits.map((h) => (
                  <li key={h.product_id} className={h.shown ? "" : "text-muted line-through"}>
                    {h.title} <span className="text-xs text-muted">distância {h.distance}</span>
                  </li>
                ))}
                <li className="pt-2 text-xs text-muted">Riscados ficam fora da loja (distância acima de {test.max_distance}).</li>
              </ul>
            )}
          </>
        )}
      </Card>
    </>
  );
}
