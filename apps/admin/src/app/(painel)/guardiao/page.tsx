import type { Metadata } from "next";
import Link from "next/link";
import { Card, PageHeader } from "@/components/ui";
import { api } from "@/lib/admin-api";
import type { Niche } from "@/lib/types";
import { GuardianForm } from "./guardian-form";

export const metadata: Metadata = { title: "Guardião" };

export default async function GuardiaoPage() {
  const niches = (await api.get<Niche[]>("/niches")).filter((n) => n.active);
  return (
    <>
      <PageHeader
        title="Guardião de IP e segurança"
        description="Teste um produto antes de cadastrar: licença, marcas, personagens, peças de segurança, material e avisos obrigatórios. Toda verificação vai para a auditoria."
      >
        <Link href="/termos" className="text-sm text-secondary hover:underline">
          ajustar termos →
        </Link>
      </PageHeader>
      <Card>
        <GuardianForm niches={niches} />
      </Card>
    </>
  );
}
