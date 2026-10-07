import type { Metadata } from "next";
import { Container, ProductGrid } from "@/components/shop";
import { storeApiOrNull, type ProductCard } from "@/lib/store";

export const metadata: Metadata = { title: "Buscar" };

export default async function BuscaPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  const query = q.trim().slice(0, 80);
  const products =
    (await storeApiOrNull<ProductCard[]>(`/products?limit=60${query ? `&q=${encodeURIComponent(query)}` : ""}`)) ?? [];
  return (
    <Container className="py-10">
      <form className="mb-8">
        <input
          name="q"
          defaultValue={query}
          autoFocus
          placeholder="O que você procura?"
          className="w-full rounded-2xl border border-border bg-surface px-5 py-4 text-lg outline-none focus:border-secondary"
        />
      </form>
      <h1 className="mb-6 font-heading text-2xl font-bold">{query ? `Resultados para “${query}”` : "Catálogo completo"}</h1>
      <ProductGrid products={products} empty="Não encontramos nada com esse termo. Tente outra palavra." />
    </Container>
  );
}
