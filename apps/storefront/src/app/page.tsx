import Link from "next/link";
import { Container, ProductGrid, whatsappLink } from "@/components/shop";
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
      <section className="bg-soft">
        <Container className="grid items-center gap-10 py-12 md:grid-cols-2 md:py-16">
          <div className="space-y-6">
            <div className="flex flex-wrap gap-2">
              <span className="seal">feito sob encomenda</span>
              <span className="seal">personalizado com carinho</span>
            </div>
            <h1 className="text-[clamp(2.5rem,6vw,4.5rem)] leading-[1.05] tracking-tight">
              {hero.title || brand.tagline || "Peças impressas em 3D, feitas para você"}
            </h1>
            <p className="max-w-xl text-xl text-muted">{hero.subtitle || "Personalize com nome, cor e tamanho. Veja em 3D antes de comprar."}</p>
            <div className="flex flex-wrap gap-3 pt-2">
              <Link href={hero.cta_href || "/busca"} className="btn w-full sm:w-auto">
                {hero.cta_label || "Ver catálogo"}
              </Link>
              {brand.contact_whatsapp && (
                <a href={whatsappLink(brand.contact_whatsapp)} target="_blank" rel="noreferrer" className="btn-outline w-full sm:w-auto">
                  Pedir pelo WhatsApp
                </a>
              )}
            </div>
          </div>
          {hero.image ? (
            // eslint-disable-next-line @next/next/no-img-element -- imagem WebP otimizada pela API
            <img src={hero.image} alt="" className="aspect-[4/3] w-full rounded-3xl object-cover shadow-card" />
          ) : (
            <div className="grid grid-cols-3 gap-3 text-5xl">
              {["✝️", "🔑", "🎁", "📦", "🚗", "🐶"].map((e) => (
                <div key={e} className="card flex aspect-square items-center justify-center">
                  {e}
                </div>
              ))}
            </div>
          )}
        </Container>
      </section>

      {active.length > 0 && (
        <Container className="py-12">
          <h2 className="mb-6 text-3xl sm:text-4xl">Escolha por tema</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {active.map((n) => (
              <Link key={n.slug} href={`/c/${n.slug}`} className="card p-5 transition hover:-translate-y-1">
                <span className="text-3xl">{NICHE_EMOJI[n.slug] ?? "✨"}</span>
                <p className="mt-2 font-heading text-lg font-semibold">{n.name}</p>
                <p className="text-sm text-muted">{n.products} produto(s)</p>
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
              <h2 className="text-3xl sm:text-4xl">{s.title}</h2>
              {s.href && (
                <Link href={s.href} className="font-bold text-primary underline decoration-2 hover:text-ink">
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
