import type { Metadata } from "next";
import Link from "next/link";
import { createCollection, type Collection } from "@/actions/library";
import { Flash } from "@/components/flash";
import { Badge, Button, Card, Empty, Label, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/admin-api";
import type { Niche } from "@/lib/types";

export const metadata: Metadata = { title: "Biblioteca" };
export const dynamic = "force-dynamic";

const STATUS: Record<Collection["status"], { label: string; tone: "ok" | "warn" | "danger" | "muted" }> = {
  vazio: { label: "sem arquivos", tone: "muted" },
  processando: { label: "processando", tone: "warn" },
  pronto: { label: "pronto", tone: "ok" },
  erro: { label: "erro", tone: "danger" },
};

export default async function BibliotecaPage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const [collections, niches] = await Promise.all([api.get<Collection[]>("/library/collections"), api.get<Niche[]>("/niches")]);
  return (
    <>
      <PageHeader
        title="Biblioteca de modelos"
        description="Acervos que você comprou ou baixou: envie os arquivos, o sistema organiza, mede e mostra cada peça. Daí é um clique para virar produto."
      />
      <Flash {...await searchParams} />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="space-y-3">
          {collections.length === 0 && <Empty>Nenhuma coleção ainda. Crie a primeira ao lado.</Empty>}
          {collections.map((c) => (
            <Link
              key={c.slug}
              href={`/biblioteca/${c.slug}`}
              className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface p-4 text-sm hover:border-secondary"
            >
              <span className="font-medium">{c.title}</span>
              <Badge tone={STATUS[c.status].tone}>{STATUS[c.status].label}</Badge>
              {!c.license_text && <Badge tone="warn">sem licença</Badge>}
              <span className="ml-auto text-muted">
                {c.models} modelo(s) · {c.products} produto(s)
                {c.pending_files.length > 0 && ` · ${c.pending_files.length} arquivo(s) a processar`}
              </span>
            </Link>
          ))}
        </div>
        <Card title="Nova coleção">
          <form action={createCollection} className="space-y-3">
            <Label label="Nome" hint="ex.: Acervo Católico — Terços">
              <input name="title" required minLength={2} className={inputClass} />
            </Label>
            <Label label="Nicho">
              <select name="niche" required className={inputClass} defaultValue="religioso">
                {niches.map((n) => (
                  <option key={n.slug} value={n.slug}>
                    {n.name}
                  </option>
                ))}
              </select>
            </Label>
            <Label label="Categoria dos produtos" hint="slug, ex.: tercos, crucifixos, presepios">
              <input name="category" required className={inputClass} />
            </Label>
            <Label label="Descrição (opcional)">
              <textarea name="description" rows={2} className={inputClass} />
            </Label>
            <Label label="Licença" hint="o que a compra permite; vazio = produtos bloqueados até você preencher">
              <input name="license_text" placeholder="ex.: licença comercial — compra em 07/10/2026" className={inputClass} />
            </Label>
            <Button type="submit">Criar coleção</Button>
          </form>
        </Card>
      </div>
    </>
  );
}
