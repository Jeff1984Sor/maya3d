import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Container } from "@/components/shop";
import { NICHE_EMOJI } from "@/lib/format";
import { StoreApiError, storeApi, type Product } from "@/lib/store";
import { BuyBox } from "./buy-box";
import { Gallery } from "./gallery";

export const revalidate = 60;
type Params = Promise<{ slug: string }>;

async function load(slug: string): Promise<Product | null> {
  try {
    return await storeApi<Product>(`/products/${encodeURIComponent(slug)}`, { revalidate: 60 });
  } catch (error) {
    if (error instanceof StoreApiError && error.status === 404) return null;
    throw error;
  }
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const product = await load((await params).slug);
  return product ? { title: product.title, description: product.description?.slice(0, 160) } : { title: "Produto" };
}

export default async function ProductPage({ params }: { params: Params }) {
  const product = await load((await params).slug);
  if (!product) notFound();

  return (
    <Container className="grid gap-10 py-10 lg:grid-cols-2">
      <Gallery images={product.images ?? []} fallback={NICHE_EMOJI[product.niche] ?? "✨"} title={product.title} />
      <div className="space-y-6">
        <div>
          <Link href={`/c/${product.niche}`} className="text-sm text-muted hover:text-ink">
            ← {product.category.replace(/-/g, " ")}
          </Link>
          <h1 className="mt-2 font-heading text-3xl font-bold tracking-tight">{product.title}</h1>
        </div>

        {product.parametric_model && (
          <Link
            href={`/personalizar/${product.slug}`}
            className="flex items-center justify-between rounded-2xl border border-secondary bg-secondary/10 p-4 font-medium text-secondary"
          >
            Personalize e veja em 3D antes de comprar <span>→</span>
          </Link>
        )}

        <BuyBox product={product} />

        {product.description && <p className="whitespace-pre-line leading-relaxed text-muted">{product.description}</p>}

        {(product.disclaimers.length > 0 || product.age_rating || product.attribution) && (
          <ul className="space-y-1 rounded-2xl border border-border bg-surface p-4 text-sm text-muted">
            {product.age_rating && <li>Classificação: {product.age_rating} · item decorativo/colecionável</li>}
            {product.disclaimers.map((d) => (
              <li key={d}>• {d}</li>
            ))}
            {product.attribution && <li>Créditos do modelo: {product.attribution}</li>}
          </ul>
        )}
      </div>
    </Container>
  );
}
