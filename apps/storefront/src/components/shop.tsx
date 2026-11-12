import Link from "next/link";
import type { ReactNode } from "react";
import type { BrandFonts } from "@print3d/shared";
import { money, NICHE_EMOJI } from "@/lib/format";
import type { Niche, PageLink, ProductCard } from "@/lib/store";

/** Peças da vitrine. Cores, fontes e logo vêm da marca (painel → Marca); aqui só a forma. */

export function Container({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-6xl px-4 sm:px-6 ${className}`}>{children}</div>;
}

export function Announcement({ freeMin, text }: { freeMin: string | null; text?: string | null }) {
  // texto do painel (Loja → página inicial) vence o aviso automático de frete
  const message = text || (freeMin ? `Entrega grátis em Sorocaba nas compras a partir de ${money(freeMin)}` : null);
  if (!message) return null;
  return <div className="bg-deep px-4 py-2 text-center text-xs font-bold text-bg sm:text-sm">{message}</div>;
}

/** Logo da marca: imagem e, se a marca pedir, o nome ao lado (última letra na cor de detalhe). */
export function BrandMark({ brand, logo, logoText, dark = false }: { brand: string; logo?: string | null; logoText: BrandFonts["logoText"]; dark?: boolean }) {
  const showName = !logo || logoText !== "";
  const name = logoText === "nome-destaque" ? brand.toLocaleLowerCase("pt-BR") : brand;
  const highlight = logoText === "nome-destaque" && name.length > 1;
  return (
    <span className={`inline-flex items-center gap-3 font-heading text-[1.625rem] font-semibold leading-none tracking-tight sm:text-[2rem] ${dark ? "text-bg" : "text-ink"}`}>
      {logo && (
        // eslint-disable-next-line @next/next/no-img-element -- imagem já otimizada (WebP) pela API
        <img src={logo} alt={showName ? "" : brand} className={showName ? "size-9 sm:size-10" : "h-10 w-auto"} />
      )}
      {showName &&
        (highlight ? (
          <span>
            {name.slice(0, -1)}
            <span className="text-accent">{name.slice(-1)}</span>
          </span>
        ) : (
          <span>{name}</span>
        ))}
    </span>
  );
}

export function Header({
  brand,
  logo,
  logoText,
  niches,
  cartCount,
}: {
  brand: string;
  logo?: string | null;
  logoText: BrandFonts["logoText"];
  niches: Niche[];
  cartCount: number;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-bg/90 backdrop-blur">
      <Container className="flex min-h-[72px] items-center gap-4 py-3">
        <Link href="/" aria-label={`${brand}: página inicial`} className="shrink-0">
          <BrandMark brand={brand} logo={logo} logoText={logoText} />
        </Link>
        <form action="/busca" className="hidden flex-1 sm:block">
          <input
            name="q"
            placeholder="Busque: santo, chaveiro com nome, suporte de celular…"
            className="w-full rounded-full border-2 border-border bg-surface px-5 py-2.5 text-sm outline-none focus:border-accent"
          />
        </form>
        <Link href="/carrinho" className="ml-auto inline-flex min-h-11 items-center rounded-full border-2 border-ink px-5 text-sm font-extrabold hover:bg-ink hover:text-bg sm:ml-0">
          Carrinho
          {cartCount > 0 && <span className="ml-2 rounded-full bg-primary px-2 text-xs leading-5 text-white">{cartCount}</span>}
        </Link>
      </Container>
      <Container className="flex gap-2 overflow-x-auto pb-3 text-sm">
        {niches
          .filter((n) => n.products > 0)
          .map((n) => (
            <Link key={n.slug} href={`/c/${n.slug}`} className="chip">
              {NICHE_EMOJI[n.slug] ?? "•"} {n.name}
            </Link>
          ))}
      </Container>
    </header>
  );
}

export function Footer({
  brand,
  logo,
  logoText,
  tagline,
  pages = [],
  email,
  whatsapp,
  social = {},
}: {
  brand: string;
  logo?: string | null;
  logoText: BrandFonts["logoText"];
  tagline?: string | null;
  pages?: PageLink[];
  email?: string | null;
  whatsapp?: string | null;
  social?: Record<string, string>;
}) {
  const links = Object.entries(social).filter(([, url]) => url.startsWith("https://"));
  return (
    <footer className="mt-20 bg-deep text-bg">
      <Container className="grid gap-10 py-12 text-sm sm:grid-cols-3">
        <div className="space-y-3">
          <BrandMark brand={brand} logo={logo} logoText={logoText} dark />
          <p className="opacity-80">{tagline || "Peças impressas em 3D, feitas sob encomenda e personalizadas."}</p>
        </div>
        <div className="space-y-2">
          <p className="font-heading text-lg font-semibold">Compra segura</p>
          <p className="opacity-80">Pix com desconto · acompanhamento do pedido em tempo real</p>
          <p className="opacity-80">Linhas de camada podem aparecer: é a marca da impressão 3D, não um defeito.</p>
        </div>
        <div className="space-y-2">
          <p className="font-heading text-lg font-semibold">Fale com a gente</p>
          {whatsapp && (
            <a href={whatsappLink(whatsapp)} className="block hover:text-accent">
              WhatsApp {whatsapp}
            </a>
          )}
          {email && (
            <a href={`mailto:${email}`} className="block hover:text-accent">
              {email}
            </a>
          )}
          {links.length > 0 && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1">
              {links.map(([name, url]) => (
                <a key={name} href={url} target="_blank" rel="noreferrer" className="capitalize hover:text-accent">
                  {name}
                </a>
              ))}
            </div>
          )}
        </div>
      </Container>
      {pages.length > 0 && (
        <Container className="flex flex-wrap gap-x-6 gap-y-2 border-t border-bg/15 py-5 text-sm">
          {pages.map((p) => (
            <Link key={p.slug} href={`/pagina/${p.slug}`} className="opacity-80 hover:text-accent hover:opacity-100">
              {p.title}
            </Link>
          ))}
        </Container>
      )}
    </footer>
  );
}

/** wa.me só com dígitos (o número vem do painel → Marca). */
export function whatsappLink(phone: string): string {
  return `https://wa.me/${phone.replace(/\D/g, "")}`;
}

/** Botão flutuante do WhatsApp; com o assistente ligado, fica acima do botão dele. */
export function WhatsAppButton({ phone, raised }: { phone: string; raised: boolean }) {
  return (
    <a
      href={whatsappLink(phone)}
      target="_blank"
      rel="noreferrer"
      aria-label="Falar no WhatsApp"
      className={`fixed right-4 z-40 grid size-14 place-items-center rounded-full bg-primary text-white shadow-card transition hover:brightness-90 ${raised ? "bottom-24" : "bottom-4"}`}
    >
      <svg viewBox="0 0 24 24" className="size-7" fill="currentColor" aria-hidden="true">
        <path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8s-.4-.1-.6.1-.7.8-.8 1-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.2-.4.2-.4.7-1.3a.4.4 0 0 0 0-.4l-.8-1.9c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6a2.7 2.7 0 0 0 1.8-1.2 2.2 2.2 0 0 0 .1-1.2c0-.1-.2-.2-.4-.3Z" />
      </svg>
    </a>
  );
}

export function ProductTile({ product }: { product: ProductCard }) {
  return (
    <Link href={`/p/${product.slug}`} className="card group flex flex-col transition hover:-translate-y-1">
      <div className="flex aspect-square items-center justify-center overflow-hidden bg-soft text-6xl">
        {product.image ? (
          // eslint-disable-next-line @next/next/no-img-element -- miniatura WebP já otimizada pela API
          <img src={product.image} alt={product.title} loading="lazy" className="h-full w-full object-cover transition group-hover:scale-105" />
        ) : (
          <span className="transition group-hover:scale-110">{NICHE_EMOJI[product.niche] ?? "✨"}</span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 px-5 pb-5 pt-4">
        <p className="line-clamp-2 font-heading text-lg font-semibold leading-snug">{product.title}</p>
        {product.customizable && <span className="seal">personalizável</span>}
        <p className="mt-auto pt-1 text-lg font-extrabold text-primary">
          {product.price_from ? (
            <>
              <span className="text-xs font-semibold text-muted">a partir de </span>
              {money(product.price_from)}
            </>
          ) : (
            <span className="text-sm font-semibold text-muted">sob consulta</span>
          )}
        </p>
        {product.colors.length > 0 && (
          <div className="flex gap-1">
            {product.colors.map((c) => (
              <span key={c} className="size-3.5 rounded-full border border-border" style={{ background: c }} />
            ))}
          </div>
        )}
      </div>
    </Link>
  );
}

export function ProductGrid({ products, empty }: { products: ProductCard[]; empty: string }) {
  if (products.length === 0) {
    return <p className="rounded-3xl border-2 border-dashed border-border p-10 text-center text-muted">{empty}</p>;
  }
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 sm:gap-6 lg:grid-cols-4">
      {products.map((p) => (
        <ProductTile key={p.slug} product={p} />
      ))}
    </div>
  );
}
