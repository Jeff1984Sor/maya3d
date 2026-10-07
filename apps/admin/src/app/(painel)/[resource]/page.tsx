import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { createItem } from "@/actions/resources";
import { Flash } from "@/components/flash";
import { ResourceForm } from "@/components/resource-form";
import { ResourceTable } from "@/components/resource-table";
import { Alert, Card, PageHeader } from "@/components/ui";
import { AdminApiError, api } from "@/lib/admin-api";
import { findResource } from "@/lib/resources";

type Params = Promise<{ resource: string }>;
type Search = Promise<{ ok?: string; erro?: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  return { title: findResource((await params).resource)?.title ?? "Cadastro" };
}

export default async function ResourcePage({ params, searchParams }: { params: Params; searchParams: Search }) {
  const resource = findResource((await params).resource);
  if (!resource) notFound();
  const flash = await searchParams;

  let rows: (Record<string, unknown> & { id: number })[] = [];
  let loadError: string | null = null;
  try {
    rows = await api.get(resource.apiPath);
  } catch (error) {
    loadError = error instanceof AdminApiError ? error.message : "API indisponível.";
  }

  return (
    <>
      <PageHeader title={resource.title} description={resource.description} />
      <Flash {...flash} />
      {loadError ? <Alert tone="error">{loadError}</Alert> : <ResourceTable resource={resource} rows={rows} />}
      <Card title={`Novo(a) ${resource.singular}`} className="mt-8">
        <ResourceForm fields={resource.fields} action={createItem.bind(null, resource.slug)} submitLabel="Cadastrar" />
      </Card>
    </>
  );
}
