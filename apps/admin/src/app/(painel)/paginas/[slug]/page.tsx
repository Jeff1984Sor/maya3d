import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { deletePage, savePage, type Page } from "@/actions/content";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { Flash } from "@/components/flash";
import { Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { AdminApiError, api } from "@/lib/admin-api";

export const metadata: Metadata = { title: "Página" };
export const dynamic = "force-dynamic";

export default async function PaginaPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ ok?: string; erro?: string }>;
}) {
  const { slug } = await params;
  let page: Page;
  try {
    page = await api.get<Page>(`/pages/${encodeURIComponent(slug)}`);
  } catch (error) {
    if (error instanceof AdminApiError && error.status === 404) notFound();
    throw error;
  }
  return (
    <>
      <PageHeader title={page.title} description={`Endereço na loja: /pagina/${page.slug}`}>
        <Link href="/paginas" className="text-sm text-secondary hover:underline">
          ← páginas
        </Link>
      </PageHeader>
      <Flash {...await searchParams} />
      <Card>
        <form action={savePage.bind(null, slug)} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
            <Label label="Título">
              <input name="title" required defaultValue={page.title} className={inputClass} />
            </Label>
            <Label label="Ordem">
              <input name="position" type="number" min={0} max={99} defaultValue={page.position} className={inputClass} />
            </Label>
          </div>
          <Label label="Texto" hint="## título · - item de lista · **negrito** · *itálico* · linha em branco separa parágrafos">
            <textarea name="body" rows={18} defaultValue={page.body} className={`${inputClass} font-mono text-xs`} />
          </Label>
          <div className="flex flex-wrap gap-6 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" name="published" defaultChecked={page.published} /> Publicada (aparece na loja)
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" name="in_footer" defaultChecked={page.in_footer} /> Link no rodapé
            </label>
          </div>
          <div className="flex gap-2">
            <Button type="submit">Salvar</Button>
          </div>
        </form>
        <form action={deletePage.bind(null, slug)} className="mt-4">
          <ConfirmSubmit message="Remover esta página?" className="text-sm text-primary hover:underline">
            remover página
          </ConfirmSubmit>
        </form>
      </Card>
    </>
  );
}
