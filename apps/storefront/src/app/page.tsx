import Link from "next/link";
import { Container, ProductGrid } from "@/components/shop";
import { api } from "@/lib/api";
import { NICHE_EMOJI } from "@/lib/format";
import { storeApiOrNull, type Niche, type ProductCard } from "@/lib/store";

export const revalidate = 60;

export default async function Home() {
  const [brand, niches, products] = await Promise.all([
    api.getBrandOrFallback(),
    storeApiOrNull<Niche[]>("/niches", 60),
    storeApiOrNull<ProductCard[]>("/products?limit=12", 60),
  ]);
  const active = (niches ?? []).filter((n) => n.products > 0);

  return (
    <>
      <section className="border-b border-border bg-surface">
        <Container className="grid items-center gap-8 py-14 md:grid-cols-2 md:py-20">
          <div className="space-y-5">
            <h1 className="font-heading text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
              {brand.tagline ?? "Peças impressas em 3D, feitas para você"}
            </h1>
            <p className="text-lg text-muted">Personalize com nome, cor e tamanho. Veja em 3D antes de comprar.</p>
            <div className="flex flex-wrap gap-3">
              <Link href="/busca" className="rounded-xl bg-primary px-6 py-3 font-medium text-white hover:opacity-90">
                Ver catálogo
              </Link>
              <Link href="/c/chaveiros" className="rounded-xl border border-border px-6 py-3 font-medium hover:border-secondary">
                Chaveiro com seu nome
              </Link>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 text-5xl">
            {["✝️", "🔑", "🎁", "📦", "🚗", "🐶"].map((e) => (
              <div key={e} className="flex aspect-square items-center justify-center rounded-2xl border border-border bg-bg">
                {e}
              </div>
            ))}
          </div>
        </Container>
      </section>

      {active.length > 0 && (
        <Container className="py-12">
          <h2 className="mb-5 font-heading text-2xl font-bold">Escolha por tema</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {active.map((n) => (
              <Link key={n.slug} href={`/c/${n.slug}`} className="rounded-2xl border border-border bg-surface p-5 hover:border-secondary">
                <span className="text-3xl">{NICHE_EMOJI[n.slug] ?? "✨"}</span>
                <p className="mt-2 font-medium">{n.name}</p>
                <p className="text-xs text-muted">{n.products} produto(s)</p>
              </Link>
            ))}
          </div>
        </Container>
      )}

      <Container className="py-6">
        <h2 className="mb-5 font-heading text-2xl font-bold">Novidades</h2>
        <ProductGrid products={products ?? []} empty="Nosso catálogo está sendo preparado. Volte em breve!" />
      </Container>
    </>
  );
}
