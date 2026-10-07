import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Container } from "@/components/shop";
import { StoreApiError, storeApi, type Product } from "@/lib/store";
import { Personalizer } from "./personalizer";

export const metadata: Metadata = { title: "Personalizar" };

export default async function PersonalizarPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let product: Product;
  try {
    product = await storeApi<Product>(`/products/${encodeURIComponent(slug)}`);
  } catch (error) {
    if (error instanceof StoreApiError && error.status === 404) notFound();
    throw error;
  }
  if (!product.parametric_model) notFound();
  return (
    <Container className="py-10">
      <h1 className="mb-2 font-heading text-3xl font-bold">{product.title}</h1>
      <p className="mb-8 text-muted">Monte do seu jeito e veja a peça girando em 3D antes de comprar.</p>
      <Personalizer product={product} />
    </Container>
  );
}
