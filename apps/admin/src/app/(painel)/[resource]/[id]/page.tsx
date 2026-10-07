import Link from "next/link";
import { notFound } from "next/navigation";
import { updateItem } from "@/actions/resources";
import { Flash } from "@/components/flash";
import { ResourceForm } from "@/components/resource-form";
import { Card, PageHeader } from "@/components/ui";
import { AdminApiError, api } from "@/lib/admin-api";
import { findResource } from "@/lib/resources";

type Params = Promise<{ resource: string; id: string }>;
type Search = Promise<{ ok?: string; erro?: string }>;

export default async function EditPage({ params, searchParams }: { params: Params; searchParams: Search }) {
  const { resource: slug, id } = await params;
  const resource = findResource(slug);
  const numericId = Number(id);
  if (!resource || !Number.isInteger(numericId)) notFound();

  let item: Record<string, unknown>;
  try {
    item = await api.get(`${resource.apiPath}/${numericId}`);
  } catch (error) {
    if (error instanceof AdminApiError && error.status === 404) notFound();
    throw error;
  }

  return (
    <>
      <PageHeader title={`Editar ${resource.singular}`} description={String(item[resource.titleField] ?? "")}>
        <Link href={`/${resource.slug}`} className="text-sm text-secondary hover:underline">
          ← voltar para {resource.title.toLowerCase()}
        </Link>
      </PageHeader>
      <Flash {...await searchParams} />
      <Card>
        <ResourceForm
          fields={resource.fields}
          values={item}
          action={updateItem.bind(null, resource.slug, numericId)}
          submitLabel="Salvar alterações"
        />
      </Card>
    </>
  );
}
