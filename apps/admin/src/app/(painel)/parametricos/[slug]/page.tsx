import Link from "next/link";
import { notFound } from "next/navigation";
import { Card, PageHeader } from "@/components/ui";
import { api } from "@/lib/admin-api";
import { schemaFields } from "@/lib/schema-form";
import type { ModelInfo } from "@/lib/types";
import { Studio } from "./studio";

export default async function ModelPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const model = (await api.get<ModelInfo[]>("/parametric")).find((m) => m.slug === slug);
  if (!model) notFound();

  return (
    <>
      <PageHeader title={model.title} description={model.description}>
        <Link href="/parametricos" className="text-sm text-secondary hover:underline">
          ← todos os modelos
        </Link>
      </PageHeader>
      <Card>
        <Studio slug={model.slug} fields={schemaFields(model.params_schema)} />
      </Card>
    </>
  );
}
