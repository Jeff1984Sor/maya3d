import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Container, ProductGrid } from "@/components/shop";
import { categoryLabel, NICHE_EMOJI } from "@/lib/format";
import { storeApiOrNull, type Niche, type ProductCard } from "@/lib/store";

export const revalidate = 60;
type Params = Promise<{ niche: string }>;
const PAGE = 60; // limite por chamada da API
const MAX_PAGES = 10;

async function findNiche(slug: string) {
  return (await storeApiOrNull<Niche[]>("/niches", 60))?.find((n) => n.slug === slug);
}

/** Todos os produtos do tema (a API entrega em lotes de 60). */
async function allProducts(slug: string): Promise<ProductCard[]> {
  const out: ProductCard[] = [];
  for (let page = 0; page < MAX_PAGES; page++) {
    const batch = await storeApiOrNull<ProductCard[]>(
      `/products?niche=${encodeURIComponent(slug)}&limit=${PAGE}&offset=${page * PAGE}`,
      60,
    );
    if (!batch?.length) break;
    out.push(...batch);
    if (batch.length < PAGE) break;
  }
  return out;
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const niche = await findNiche((await params).niche);
  return { title: niche?.name ?? "Catálogo" };
}

export default async function NichePage({ params }: { params: Params }) {
  const { niche: slug } = await params;
  const niche = await findNiche(slug);
  if (!niche) notFound();
  const products = await allProducts(slug);
  // separa por categoria (Natal, Páscoa, Terços...): a maior primeiro
  const groups = new Map<string, ProductCard[]>();
  for (const p of products) groups.set(p.category, [...(groups.get(p.category) ?? []), p]);
  const sorted = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
  const anchor = (category: string) => `cat-${category}`;

  return (
    <Container className="py-10">
      <h1 className="mb-6 text-4xl sm:text-5xl">
        {NICHE_EMOJI[slug] ?? ""} {niche.name}
      </h1>
      {sorted.length > 1 && (
        <nav aria-label="Categorias" className="mb-10 flex flex-wrap gap-2">
          {sorted.map(([category, items]) => (
            <a key={category} href={`#${anchor(category)}`} className="chip">
              {categoryLabel(category)} <span className="text-xs font-semibold text-muted">{items.length}</span>
            </a>
          ))}
        </nav>
      )}
      {sorted.length === 0 ? (
        <ProductGrid products={[]} empty="Nenhum produto disponível neste tema ainda." />
      ) : (
        <div className="space-y-14">
          {sorted.map(([category, items]) => (
            <section key={category} id={anchor(category)} className="scroll-mt-40">
              {sorted.length > 1 && <h2 className="mb-6 text-3xl">{categoryLabel(category)}</h2>}
              <ProductGrid products={items} empty="" />
            </section>
          ))}
        </div>
      )}
    </Container>
  );
}
