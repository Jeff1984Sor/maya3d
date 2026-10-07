import type { Metadata } from "next";
import Link from "next/link";
import { Card, Empty, PageHeader } from "@/components/ui";
import { api } from "@/lib/admin-api";
import type { Material, Printer } from "@/lib/types";
import { CompareForm } from "./compare-form";

export const metadata: Metadata = { title: "Comparativo de materiais" };

export default async function ComparativoPage({
  searchParams,
}: {
  searchParams: Promise<{ ref?: string; grams?: string; hours?: string; post?: string; category?: string }>;
}) {
  const [materials, printers, prefill] = await Promise.all([
    api.get<Material[]>("/materials"),
    api.get<Printer[]>("/printers"),
    searchParams,
  ]);
  return (
    <>
      <PageHeader
        title="Comparativo de materiais"
        description="A mesma peça em cada material: as gramas mudam com a densidade (mesmo volume), e daí o custo, o preço e o lucro em cada canal."
      />
      {materials.length < 2 || printers.length === 0 ? (
        <Empty>
          Cadastre pelo menos dois <Link className="text-secondary" href="/materiais">materiais</Link> e uma{" "}
          <Link className="text-secondary" href="/impressoras">impressora</Link> para comparar.
        </Empty>
      ) : (
        <Card>
          <CompareForm materials={materials} printers={printers} prefill={prefill} />
        </Card>
      )}
    </>
  );
}
