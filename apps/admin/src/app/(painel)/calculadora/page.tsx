import type { Metadata } from "next";
import Link from "next/link";
import { Card, Empty, PageHeader } from "@/components/ui";
import { api } from "@/lib/admin-api";
import type { Material, Printer } from "@/lib/types";
import { QuoteForm } from "./quote-form";

export const metadata: Metadata = { title: "Calculadora de preço" };

export default async function CalculadoraPage() {
  const [materials, printers] = await Promise.all([
    api.get<Material[]>("/materials"),
    api.get<Printer[]>("/printers"),
  ]);
  const missing = materials.length === 0 || printers.length === 0;

  return (
    <>
      <PageHeader
        title="Calculadora de preço"
        description="Custo detalhado e preço com lucro líquido em cada canal. Gramas e tempo virão do fatiador; por enquanto, informe os do seu fatiador."
      />
      {missing ? (
        <Empty>
          Cadastre ao menos um <Link className="text-secondary" href="/materiais">material</Link> e uma{" "}
          <Link className="text-secondary" href="/impressoras">impressora</Link> (pode ser “planejada”) para calcular.
        </Empty>
      ) : (
        <Card>
          <QuoteForm materials={materials} printers={printers} />
        </Card>
      )}
    </>
  );
}
