import type { Metadata } from "next";
import Link from "next/link";
import { savePage, type Page } from "@/actions/content";
import { Flash } from "@/components/flash";
import { Badge, Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/admin-api";

export const metadata: Metadata = { title: "Páginas" };
export const dynamic = "force-dynamic";

export default async function PaginasPage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const pages = await api.get<Page[]>("/pages");
  return (
    <>
      <PageHeader title="Páginas da loja" description="Sobre, trocas e devoluções, privacidade… Os rascunhos já vieram prontos: revise e publique." />
      <Flash {...await searchParams} />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-2">
          {pages.map((p) => (
            <Link
              key={p.slug}
              href={`/paginas/${p.slug}`}
              className="flex items-center gap-3 rounded-xl border border-border bg-surface p-4 text-sm hover:border-secondary"
            >
              <span className="font-medium">{p.title}</span>
              <span className="text-xs text-muted">/pagina/{p.slug}</span>
              <span className="ml-auto flex gap-2">
                <Badge tone={p.published ? "ok" : "warn"}>{p.published ? "publicada" : "rascunho"}</Badge>
                {p.in_footer && <Badge>no rodapé</Badge>}
              </span>
            </Link>
          ))}
        </div>
        <Card title="Nova página">
          <form action={savePage.bind(null, null)} className="space-y-3">
            <Label label="Título">
              <input name="title" required className={inputClass} />
            </Label>
            <Label label="Endereço" hint="minúsculas e hífen, ex.: perguntas-frequentes">
              <input name="slug" required pattern="[a-z0-9-]{2,80}" className={inputClass} />
            </Label>
            <input type="hidden" name="in_footer" value="on" />
            <Button type="submit">Criar</Button>
          </form>
        </Card>
      </div>
    </>
  );
}
