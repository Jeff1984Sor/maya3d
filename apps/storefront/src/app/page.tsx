import Link from "next/link";
import { Container, ProductGrid } from "@/components/shop";
import { api } from "@/lib/api";
import { NICHE_EMOJI } from "@/lib/format";
import { storeApiOrNull, type Home as HomeData, type Niche } from "@/lib/store";

export const revalidate = 60;

/** Página inicial montada no painel (Loja → página inicial). Sem configuração: padrão. */
export default async function Home() {
  const [brand, niches, home] = await Promise.all([
    api.getBrandOrFallback(),
    storeApiOrNull<Niche[]>("/niches", 60),
    storeApiOrNull<HomeData>("/home", 60),
  ]);
  const active = (niches ?? []).filter((n) => n.products > 0);
  const hero = home?.hero ?? {};
  const sections = home?.sections ?? [];

  return (
    <>
      <section className="border-b border-border bg-surface">
        <Container className="grid items-center gap-8 py-14 md:grid-cols-2 md:py-20">
          <div className="space-y-5">
            <h1 className="font-heading text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
              {hero.title || brand.tagline || "Peças impressas em 3D, feitas para você"}
            </h1>
            <p className="text-lg text-muted">{hero.subtitle || "Personalize com nome, cor e tamanho. Veja em 3D antes de comprar."}</p>
            <div className="flex flex-wrap gap-3">
              <Link href={hero.cta_href || "/busca"} className="rounded-xl bg-primary px-6 py-3 font-medium text-white hover:opacity-90">
                {hero.cta_label || "Ver catálogo"}
              </Link>
            </div>
          </div>
          {hero.image ? (
            // eslint-disable-next-line @next/next/no-img-element -- imagem WebP otimizada pela API
            <img src={hero.image} alt="" className="aspect-[4/3] w-full rounded-3xl object-cover" />
          ) : (
            <div className="grid grid-cols-3 gap-3 text-5xl">
              {["✝️", "🔑", "🎁", "📦", "🚗", "🐶"].map((e) => (
                <div key={e} className="flex aspect-square items-center justify-center rounded-2xl border border-border bg-bg">
                  {e}
                </div>
              ))}
            </div>
          )}
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

      {sections.length === 0 ? (
        <Container className="py-6">
          <ProductGrid products={[]} empty="Nosso catálogo está sendo preparado. Volte em breve!" />
        </Container>
      ) : (
        sections.map((s) => (
          <Container key={s.title} className="py-6">
            <div className="mb-5 flex items-baseline justify-between gap-4">
              <h2 className="font-heading text-2xl font-bold">{s.title}</h2>
              {s.href && (
                <Link href={s.href} className="text-sm text-secondary hover:underline">
                  ver tudo →
                </Link>
              )}
            </div>
            <ProductGrid products={s.products} empty="" />
          </Container>
        ))
      )}
    </>
  );
}
