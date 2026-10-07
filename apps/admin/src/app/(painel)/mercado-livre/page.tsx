import type { Metadata } from "next";
import Link from "next/link";
import { answerQuestion, connectMl, disconnectMl, type MlListing, type MlQuestion, type MlStatus } from "@/actions/mercadolivre";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { Flash } from "@/components/flash";
import { MlHero, ML_COLORS } from "@/components/ml-brand";
import { Badge, Button, Card, Empty, inputClass } from "@/components/ui";
import { api } from "@/lib/admin-api";
import { formatMoney } from "@/lib/form";

export const metadata: Metadata = { title: "Mercado Livre" };
export const dynamic = "force-dynamic";

function Step({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <span>{ok ? "✅" : "⬜"}</span>
      <span className={ok ? "text-muted" : ""}>{children}</span>
    </li>
  );
}

export default async function MercadoLivrePage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const [status, listings, questions] = await Promise.all([
    api.get<MlStatus>("/mercadolivre/status"),
    api.get<MlListing[]>("/mercadolivre/listings"),
    api.get<MlQuestion[]>("/mercadolivre/questions"),
  ]);
  const pending = questions.filter((q) => q.status === "pendente");
  return (
    <>
      <MlHero title="Mercado Livre" subtitle="Conta conectada, anúncios e perguntas. Pedidos pagos entram sozinhos na Produção.">
        {status.connected ? (
          <span className="rounded-full bg-white/70 px-4 py-1.5 text-sm font-semibold">● conectado {status.nickname && `· ${status.nickname}`}</span>
        ) : (
          <span className="rounded-full bg-white/60 px-4 py-1.5 text-sm font-semibold">não conectado</span>
        )}
      </MlHero>
      <Flash {...await searchParams} />

      <Card title="Conexão" className="mb-6">
        <ol className="mb-4 space-y-1 text-sm">
          <Step ok={status.https_ready}>
            Domínio com HTTPS e endereço público da API em <Link className="text-secondary hover:underline" href="/integracoes">Integrações</Link>
          </Step>
          <Step ok={status.configured}>
            Aplicação criada no portal de desenvolvedores do ML (App ID e chave secreta em Integrações). Na aplicação, use o retorno{" "}
            <code className="text-xs">https://api.&lt;domínio&gt;{status.callback_path}</code> e as notificações em{" "}
            <code className="text-xs">https://api.&lt;domínio&gt;{status.webhook_path}</code> (tópicos orders_v2 e questions)
          </Step>
          <Step ok={status.pictures_ready}>Endereço público da loja (fotos dos anúncios)</Step>
          <Step ok={status.connected}>Conta conectada {status.nickname && <b>({status.nickname})</b>}</Step>
        </ol>
        <div className="flex gap-2">
          <form action={connectMl}>
            <button
              disabled={!status.configured || !status.https_ready}
              className="rounded-xl px-5 py-2.5 text-sm font-bold shadow-sm transition hover:brightness-95 disabled:opacity-50"
              style={{ background: ML_COLORS.yellow, color: ML_COLORS.navy }}
            >
              {status.connected ? "Reconectar" : "Conectar conta do Mercado Livre"}
            </button>
          </form>
          {status.connected && (
            <form action={disconnectMl}>
              <ConfirmSubmit message="Desconectar a conta? Os anúncios continuam no ML, mas o sistema para de receber pedidos." className="rounded-xl px-4 py-2 text-sm text-primary hover:bg-primary/10">
                Desconectar
              </ConfirmSubmit>
            </form>
          )}
        </div>
        {status.status === "erro" && <p className="mt-3 text-sm text-primary">A renovação do acesso falhou: reconecte a conta.</p>}
      </Card>

      <Card title={`Perguntas (${pending.length} pendente${pending.length === 1 ? "" : "s"})`} className="mb-6">
        <p className="mb-3 text-xs text-muted">Responda só pelo Mercado Livre: não passe telefone, WhatsApp, e-mail nem links (regra da plataforma).</p>
        {questions.length === 0 ? (
          <Empty>Nenhuma pergunta ainda.</Empty>
        ) : (
          <ul className="space-y-3">
            {questions.map((q) => (
              <li key={q.id} className="rounded-xl border border-border p-3 text-sm">
                <div className="mb-1 flex items-center gap-2">
                  <Badge tone={q.status === "pendente" ? "warn" : "ok"}>{q.status}</Badge>
                  {q.product_id && (
                    <Link href={`/produtos/${q.product_id}`} className="text-xs text-secondary hover:underline">
                      ver produto
                    </Link>
                  )}
                </div>
                <p className="font-medium">“{q.text}”</p>
                {q.answer && <p className="mt-1 text-muted">↳ {q.answer}</p>}
                {q.status === "pendente" && (
                  <form action={answerQuestion.bind(null, q.id)} className="mt-2 flex gap-2">
                    <input name="text" required minLength={2} maxLength={2000} placeholder="Sua resposta" className={inputClass} />
                    <Button>Responder</Button>
                  </form>
                )}
              </li>
            ))}
          </ul>
        )}
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
                  <td>{l.listing_type === "gold_pro" ? "Premium" : "Clássico"}</td>
                  <td>{formatMoney(l.price)}</td>
                  <td>{l.fee ? `tarifa ${formatMoney(l.fee)}` : ""}</td>
                  <td>
                    <Badge tone={l.status === "publicado" ? "ok" : l.status === "erro" ? "danger" : "muted"}>{l.status}</Badge>
                  </td>
                  <td className="max-w-xs truncate text-xs text-primary">{l.last_error}</td>
                  <td>
                    {l.permalink && (
                      <a href={l.permalink} target="_blank" rel="noreferrer" className="text-secondary hover:underline">
                        abrir
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
