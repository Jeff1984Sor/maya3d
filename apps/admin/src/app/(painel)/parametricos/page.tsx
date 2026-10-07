import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { api } from "@/lib/admin-api";
import type { ModelInfo } from "@/lib/types";

export const metadata: Metadata = { title: "Paramétricos" };

export default async function ParametricosPage() {
  const models = await api.get<ModelInfo[]>("/parametric");
  return (
    <>
      <PageHeader
        title="Modelos paramétricos"
        description="Peças próprias geradas por parâmetros: sem licença de terceiros, prontas para personalização. Textos passam pelo Guardião."
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {models.map((m) => (
          <Link
            key={m.slug}
            href={`/parametricos/${m.slug}`}
            className="rounded-2xl border border-border bg-surface p-5 transition hover:border-secondary"
          >
            <p className="text-xs uppercase tracking-widest text-muted">{m.niche}</p>
            <p className="mt-1 font-heading text-lg font-semibold">{m.title}</p>
            <p className="mt-2 text-sm text-muted">{m.description}</p>
          </Link>
        ))}
      </div>
    </>
  );
}
