import type { Metadata } from "next";
import Link from "next/link";
import { clearIntegration, generateIntegration, saveIntegrations, testWhatsapp, type IntegrationField } from "@/actions/integrations";
import { Flash } from "@/components/flash";
import { Badge, Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/admin-api";

export const metadata: Metadata = { title: "Integrações" };
export const dynamic = "force-dynamic";

const GROUPS = [
  {
    id: "ia",
    title: "Inteligência artificial",
    help: "Cole a chave da OpenAI (ou Anthropic). Depois escolha os modelos na tela IA.",
    next: { href: "/ia", label: "escolher modelos →" },
  },
  {
    id: "whatsapp",
    title: "WhatsApp (API oficial da Meta)",
    help: "Dados do app no Meta for Developers → WhatsApp → Configuração da API. Envio funciona já; respostas e botões precisam do domínio com HTTPS (webhook /v1/webhooks/whatsapp).",
    next: { href: "/mensagens", label: "caixa de saída →" },
  },
  {
    id: "geral",
    title: "Endereços públicos (domínio)",
    help: "Quando o domínio estiver no ar com HTTPS: endereço da API e da loja. Os marketplaces e a Meta usam estes endereços para retorno, avisos e fotos.",
    next: { href: "/mercado-livre", label: "Mercado Livre →" },
  },
  {
    id: "mercadolivre",
    title: "Mercado Livre",
    help: "Crie uma aplicação no portal de desenvolvedores do Mercado Livre e cole o App ID e a chave secreta. Depois conecte a conta na página Mercado Livre.",
    next: { href: "/mercado-livre", label: "conectar conta →" },
  },
  {
    id: "shopee",
    title: "Shopee",
    help: "Crie um app na Shopee Open Platform e cole o Partner ID e a Partner Key. Depois conecte a loja na página Shopee.",
    next: { href: "/shopee", label: "conectar loja →" },
  },
  {
    id: "frete",
    title: "Frete (Melhor Envio)",
    help: "Cotação automática de Correios e transportadoras para fora de Sorocaba. Gere o token no painel do Melhor Envio e preencha também o CEP de origem em Operação.",
    next: { href: "/operacao", label: "CEP de origem →" },
  },
] as const;

function FieldInput({ f }: { f: IntegrationField }) {
  const placeholder = f.configured ? (f.secret ? `configurada (${f.preview}) — deixe vazio para manter` : "") : f.secret ? "cole aqui" : "";
  if (f.choices.length) {
    return (
      <select name={f.key} defaultValue={f.configured && !f.secret ? (f.preview ?? "") : ""} className={inputClass}>
        <option value="">—</option>
        {f.choices.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      name={f.key}
      type={f.secret ? "password" : "text"}
      autoComplete="off"
      defaultValue={f.secret ? "" : (f.preview ?? "")}
      placeholder={placeholder}
      className={inputClass}
    />
  );
}

export default async function IntegracoesPage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const fields = await api.get<IntegrationField[]>("/integrations");
  return (
    <>
      <PageHeader
        title="Integrações"
        description="Cole aqui as chaves dos serviços. Ficam guardadas cifradas no banco e nunca aparecem de novo inteiras — nem para você."
      />
      <Flash {...await searchParams} />
      <div className="space-y-6">
        {GROUPS.map((g) => {
          const group = fields.filter((f) => f.group === g.id);
          const keys = group.map((f) => f.key);
          return (
            <Card key={g.id} title={g.title}>
              <p className="mb-4 text-sm text-muted">
                {g.help}{" "}
                <Link href={g.next.href} className="text-secondary hover:underline">
                  {g.next.label}
                </Link>
              </p>
              <form action={saveIntegrations.bind(null, keys)} className="grid gap-4 sm:grid-cols-2">
                {group.map((f) => (
                  <Label key={f.key} label={f.label} hint={f.hint || undefined}>
                    <FieldInput f={f} />
                    <span className="mt-1 flex items-center gap-2 text-xs">
                      <Badge tone={f.configured ? "ok" : "muted"}>
                        {f.configured ? (f.source === "servidor" ? "configurada no servidor" : "configurada") : "vazia"}
                      </Badge>
                      {f.generatable && (
                        <Button formAction={generateIntegration.bind(null, f.key)} variant="secondary" className="px-2 py-0.5 text-xs">
                          gerar
                        </Button>
                      )}
                      {f.source === "painel" && (
                        <Button formAction={clearIntegration.bind(null, f.key)} variant="danger" className="px-2 py-0.5 text-xs">
                          remover
                        </Button>
                      )}
                    </span>
                  </Label>
                ))}
                <div className="flex flex-wrap gap-2 sm:col-span-2">
                  <Button type="submit">Salvar</Button>
                  {g.id === "whatsapp" && (
                    <Button formAction={testWhatsapp} variant="secondary">
                      Mandar teste para o meu WhatsApp
                    </Button>
                  )}
                </div>
              </form>
            </Card>
          );
        })}
      </div>
    </>
  );
}
