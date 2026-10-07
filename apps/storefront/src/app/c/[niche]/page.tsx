import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Container, ProductGrid } from "@/components/shop";
import { storeApiOrNull, type Niche, type ProductCard } from "@/lib/store";

export const revalidate = 60;
type Params = Promise<{ niche: string }>;

async function findNiche(slug: string) {
  return (await storeApiOrNull<Niche[]>("/niches", 60))?.find((n) => n.slug === slug);
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const niche = await findNiche((await params).niche);
  return { title: niche?.name ?? "Catálogo" };
}

export default async function NichePage({ params }: { params: Params }) {
  const { niche: slug } = await params;
  const niche = await findNiche(slug);
  if (!niche) notFound();
  const products = (await storeApiOrNull<ProductCard[]>(`/products?niche=${encodeURIComponent(slug)}&limit=60`, 60)) ?? [];
  return (
    <Container className="py-10">
      <h1 className="mb-6 font-heading text-3xl font-bold">{niche.name}</h1>
      <ProductGrid products={products} empty="Nenhum produto disponível neste tema ainda." />
    </Container>
  );
}
