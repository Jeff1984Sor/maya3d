import { applyCopy, editCopy, generateCopy, setCopyStatus, type ChannelCopy } from "@/actions/ai";
import { Badge, Button, Card, inputClass } from "@/components/ui";

const CHANNELS = [
  { id: "site", label: "Loja" },
  { id: "mercadolivre", label: "Mercado Livre" },
  { id: "shopee", label: "Shopee" },
  { id: "instagram", label: "Instagram" },
] as const;

const label = (c: string) => CHANNELS.find((x) => x.id === c)?.label ?? c;
const tone = (s: string) => (s === "aprovado" ? "ok" : s === "descartado" ? "muted" : "warn");

/** ✍️ Redator por canal: gera, mostra os avisos das conferências e deixa editar/aprovar. */
export function ChannelCopyPanel({ productId, copies }: { productId: number; copies: ChannelCopy[] }) {
  return (
    <Card title="✍️ Textos por canal (IA)">
      <div id="textos" />
      <form action={generateCopy.bind(null, productId)} className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        {CHANNELS.map((c) => (
          <label key={c.id} className="flex items-center gap-1">
            <input type="checkbox" name="channels" value={c.id} defaultChecked />
            {c.label}
          </label>
        ))}
        <Button type="submit" className="ml-auto">
          {copies.length ? "Refazer textos" : "Gerar textos"}
        </Button>
      </form>
      <p className="mb-4 text-xs text-muted">
        A IA usa só os dados do produto. Números que não estão nos dados, links/contatos em marketplace e termos do Guardião viram
        aviso. Nada vai para um canal sem a sua aprovação.
      </p>
      <div className="space-y-4">
        {copies.map((c) => (
          <details key={c.id} className="rounded-xl border border-border p-4" open={c.status === "rascunho"}>
            <summary className="flex cursor-pointer flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{label(c.channel)}</span>
              <Badge tone={tone(c.status)}>{c.status}</Badge>
              {c.guardian_status === "bloqueado" && <Badge tone="danger">Guardião bloqueou</Badge>}
              {c.issues.length > 0 && <Badge tone="warn">{c.issues.length} aviso(s)</Badge>}
              <span className="ml-auto truncate text-muted">{c.title}</span>
            </summary>
            {c.issues.length > 0 && (
              <ul className="mt-3 list-inside list-disc space-y-1 text-xs text-primary">
                {c.issues.map((i) => (
                  <li key={i}>{i}</li>
                ))}
              </ul>
            )}
            <form action={editCopy.bind(null, productId, c.id)} className="mt-3 space-y-3">
              <label className="block text-xs text-muted">
                Título ({c.title.length}/{c.title_max})
                <input name="title" defaultValue={c.title} className={inputClass} />
              </label>
              <label className="block text-xs text-muted">
                Descrição
                <textarea name="description" defaultValue={c.description} rows={6} className={inputClass} />
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-xs text-muted">
                  Destaques (um por linha)
                  <textarea name="bullets" defaultValue={c.bullets.join("\n")} rows={4} className={inputClass} />
                </label>
                <label className="block text-xs text-muted">
                  Palavras de busca (uma por linha)
                  <textarea name="keywords" defaultValue={c.keywords.join("\n")} rows={4} className={inputClass} />
                </label>
              </div>
              {c.channel === "instagram" && (
                <label className="block text-xs text-muted">
                  Hashtags (uma por linha, sem #)
                  <textarea name="hashtags" defaultValue={c.hashtags.join("\n")} rows={3} className={inputClass} />
                </label>
              )}
              <div className="flex flex-wrap gap-2">
                <Button type="submit" variant="secondary">
                  Salvar edição
                </Button>
                {c.status !== "aprovado" && (
                  <Button formAction={setCopyStatus.bind(null, productId, c.id, "aprovado")} disabled={c.guardian_status === "bloqueado"}>
                    Aprovar
                  </Button>
                )}
                {c.status === "aprovado" && c.channel === "site" && (
                  <Button formAction={applyCopy.bind(null, productId, c.id)}>Usar na loja</Button>
                )}
                {c.status !== "descartado" && (
                  <Button formAction={setCopyStatus.bind(null, productId, c.id, "descartado")} variant="danger">
                    Descartar
                  </Button>
                )}
              </div>
            </form>
          </details>
        ))}
      </div>
    </Card>
  );
}
