import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  clearPending,
  processCollection,
  productFromModel,
  saveLicense,
  toggleIgnore,
  type Collection,
  type LibraryModel,
} from "@/actions/library";
import { Flash } from "@/components/flash";
import { AutoRefresh, LibraryUploader } from "@/components/library-uploader";
import { Alert, Badge, Button, Card, Empty, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/admin-api";

export const metadata: Metadata = { title: "Coleção" };
export const dynamic = "force-dynamic";

const dims = (b: number[] | null) => (b ? b.map((v) => Math.round(v)).join(" × ") + " mm" : "medidas a confirmar");

export default async function ColecaoPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ ok?: string; erro?: string; ver?: string }>;
}) {
  const { slug } = await params;
  const query = await searchParams;
  const collections = await api.get<Collection[]>("/library/collections");
  const col = collections.find((c) => c.slug === slug);
  if (!col) notFound();
  const models = await api.get<LibraryModel[]>(`/library/collections/${slug}/models`);
  const view = query.ver ?? "novo";
  const shown = models.filter((m) => view === "todos" || m.status === view);
  const counts = { novo: 0, produto: 0, ignorado: 0 };
  models.forEach((m) => counts[m.status]++);

  return (
    <>
      <AutoRefresh active={col.status === "processando"} />
      <PageHeader title={col.title} description={`${col.niche} · ${col.category}${col.description ? ` · ${col.description}` : ""}`}>
        <Link href="/biblioteca" className="text-sm text-secondary hover:underline">
          ← biblioteca
        </Link>
      </PageHeader>
      <Flash ok={query.ok} erro={query.erro} />
      {col.status === "erro" && col.error && <Alert tone="error">{col.error}</Alert>}

      <div className="mb-6 grid gap-6 xl:grid-cols-2">
        <Card title="1. Enviar arquivos">
          <LibraryUploader slug={slug} />
          {col.pending_files.length > 0 && (
            <div className="mt-4 rounded-xl bg-bg p-3 text-sm">
              <p className="mb-2 font-medium">{col.pending_files.length} arquivo(s) esperando processamento</p>
              <p className="mb-3 line-clamp-3 text-xs text-muted">{col.pending_files.join(", ")}</p>
              <div className="flex gap-2">
                <form action={processCollection.bind(null, slug)}>
                  <Button disabled={col.status === "processando"}>
                    {col.status === "processando" ? "Processando…" : "2. Organizar e analisar"}
                  </Button>
                </form>
                <form action={clearPending.bind(null, slug)}>
                  <Button variant="secondary">Descartar envios</Button>
                </form>
              </div>
            </div>
          )}
          {col.status === "processando" && <p className="mt-3 text-sm text-muted">Organizando e medindo as peças… a tela atualiza sozinha.</p>}
        </Card>
        <Card title="Licença da coleção">
          <form action={saveLicense.bind(null, slug)} className="space-y-3">
            <input
              name="license_text"
              defaultValue={col.license_text ?? ""}
              placeholder="ex.: licença comercial — compra em 07/10/2026"
              className={inputClass}
            />
            <p className="text-xs text-muted">
              Escreva o que a compra permite (guarde o comprovante). Sem isso, os produtos desta coleção ficam bloqueados pelo
              Guardião. Ao salvar, todos são verificados de novo.
            </p>
            <Button type="submit" variant="secondary">
              Salvar licença
            </Button>
          </form>
        </Card>
      </div>

      <div className="mb-4 flex flex-wrap gap-2 text-sm">
        {(["novo", "produto", "ignorado", "todos"] as const).map((v) => (
          <Link
            key={v}
            href={`/biblioteca/${slug}?ver=${v}`}
            className={`rounded-full border px-3 py-1 ${view === v ? "border-secondary text-secondary" : "border-border"}`}
          >
            {v === "todos" ? `todos (${models.length})` : `${v === "novo" ? "novos" : v === "produto" ? "viraram produto" : "ignorados"} (${counts[v]})`}
          </Link>
        ))}
      </div>

      {shown.length === 0 ? (
        <Empty>{models.length ? "Nada nesta aba." : "Envie os arquivos e clique em Organizar e analisar."}</Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((m) => (
            <div key={m.id} className="flex flex-col overflow-hidden rounded-xl border border-border bg-surface">
              <div className="flex aspect-[4/3] items-center justify-center bg-white">
                {m.cover ? (
                  // eslint-disable-next-line @next/next/no-img-element -- arquivo privado servido pelo proxy autenticado
                  <img src={`/api/files/library/${slug}/modelos/${m.key}/${m.cover}`} alt={m.title} className="h-full w-full object-contain" loading="lazy" />
                ) : (
                  <span className="text-4xl">🧩</span>
                )}
              </div>
              <div className="flex flex-1 flex-col gap-2 p-4 text-sm">
                <p className="font-medium">{m.title}</p>
                <div className="flex flex-wrap gap-1">
                  <Badge>{dims(m.bbox_mm)}</Badge>
                  {m.fits === true && <Badge tone="ok">cabe na mesa</Badge>}
                  {m.fits === false && <Badge tone="warn">maior que a mesa: dividir</Badge>}
                  {m.issues.length > 0 && <Badge tone="danger">{m.issues.length} problema(s)</Badge>}
                </div>
                {m.issues.length > 0 && <p className="text-xs text-primary">{m.issues.join("; ")}</p>}
                <p className="text-xs text-muted">
                  {m.files.map((f) => (
                    <a key={f.name} href={`/api/files/library/${slug}/modelos/${m.key}/${f.name}`} className="mr-2 hover:underline">
                      {f.name.split(".").pop()?.toUpperCase()}
                    </a>
                  ))}
                </p>
                <div className="mt-auto">
                  {m.status === "produto" && m.product_id ? (
                    <Link href={`/produtos/${m.product_id}`} className="text-secondary hover:underline">
                      ver produto →
                    </Link>
                  ) : (
                    <form action={productFromModel.bind(null, slug, m.id)} className="flex gap-2">
                      <input name="title" defaultValue={m.title} className={inputClass} aria-label="Título do produto" />
                      <Button disabled={m.status === "ignorado"}>Criar produto</Button>
                      <Button formAction={toggleIgnore.bind(null, slug, m.id)} variant="secondary">
                        {m.status === "ignorado" ? "Voltar" : "Ignorar"}
                      </Button>
                    </form>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
