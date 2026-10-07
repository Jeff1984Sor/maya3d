import type { Metadata } from "next";
import Link from "next/link";
import { createProduct } from "@/actions/products";
import { Flash } from "@/components/flash";
import { ProductForm } from "@/components/product-form";
import { Card, PageHeader } from "@/components/ui";
import { api } from "@/lib/admin-api";
import type { Niche } from "@/lib/types";

export const metadata: Metadata = { title: "Novo produto" };

export default async function NovoProdutoPage({ searchParams }: { searchParams: Promise<{ erro?: string }> }) {
  const niches = (await api.get<Niche[]>("/niches")).filter((n) => n.active);
  return (
    <>
      <PageHeader title="Novo produto" description="Ao salvar, o Guardião verifica licença, marcas, segurança e avisos obrigatórios.">
        <Link href="/produtos" className="text-sm text-secondary hover:underline">
          ← produtos
        </Link>
      </PageHeader>
      <Flash {...await searchParams} />
      <Card>
        <ProductForm niches={niches} action={createProduct} submitLabel="Criar produto" />
      </Card>
    </>
  );
}
