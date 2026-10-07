import type { Metadata } from "next";
import Link from "next/link";
import { Card, Empty, PageHeader } from "@/components/ui";
import { api } from "@/lib/admin-api";
import { SplitStudio } from "./split-studio";

export const metadata: Metadata = { title: "Dividir peça grande" };

type PrinterFull = { id: number; name: string; status: string; bed_x_mm: number; bed_y_mm: number; bed_z_mm: number };

export default async function DividirPage() {
  const printers = (await api.get<PrinterFull[]>("/printers")).filter((p) => p.status !== "inativa");
  return (
    <>
      <PageHeader
        title="Dividir peça grande"
        description="Corta a peça no menor número de pedaços que cabem na impressora, com furos alinhados e pinos de encaixe para colar depois."
      />
      {printers.length === 0 ? (
        <Empty>
          Cadastre uma <Link className="text-secondary" href="/impressoras">impressora</Link> (pode ser “planejada”) para saber o tamanho da mesa.
        </Empty>
      ) : (
        <Card>
          <SplitStudio printers={printers} />
        </Card>
      )}
    </>
  );
}
