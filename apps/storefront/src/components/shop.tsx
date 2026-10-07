import Link from "next/link";
import type { ReactNode } from "react";
import { money, NICHE_EMOJI } from "@/lib/format";
import type { Niche, PageLink, ProductCard } from "@/lib/store";

/** Peças da vitrine. A loja é neutra para as peças coloridas brilharem (spec 5.1). */

export function Container({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-6xl px-4 sm:px-6 ${className}`}>{children}</div>;
}

export function Announcement({ freeMin, text }: { freeMin: string | null; text?: string | null }) {
  // texto do painel (Loja → página inicial) vence o aviso automático de frete
  const message = text || (freeMin ? `Entrega grátis em Sorocaba nas compras a partir de ${money(freeMin)}` : null);
  if (!message) return null;
  return <div className="bg-ink px-4 py-2 text-center text-xs font-medium text-bg sm:text-sm">{message}</div>;
}

export function Header({
  brand,
  logo,
  niches,
  cartCount,
}: {
  brand: string;
  logo?: string | null;
  niches: Niche[];
  cartCount: number;
}) {
  return (
    <header className="border-b border-border bg-surface/90 backdrop-blur">
      <Container className="flex items-center gap-4 py-4">
        <Link href="/" className="font-heading text-xl font-bold tracking-tight">
          {logo ? (
            // eslint-disable-next-line @next/next/no-img-element -- imagem já otimizada (WebP) pela API
            <img src={logo} alt={brand} className="h-9 w-auto" />
          ) : (
            brand
          )}
        </Link>
        <form action="/busca" className="hidden flex-1 sm:block">
          <input
            name="q"
            placeholder="Busque: santo, chaveiro com nome, suporte de celular…"
            className="w-full rounded-full border border-border bg-bg px-4 py-2 text-sm outline-none focus:border-secondary"
          />
        </form>
        <Link href="/carrinho" className="ml-auto rounded-full border border-border px-4 py-2 text-sm hover:border-primary sm:ml-0">
          Carrinho{cartCount > 0 && <span className="ml-2 rounded-full bg-primary px-2 text-white">{cartCount}</span>}
        </Link>
      </Container>
      <Container className="flex gap-2 overflow-x-auto pb-3 text-sm">
        {niches
          .filter((n) => n.products > 0)
          .map((n) => (
            <Link key={n.slug} href={`/c/${n.slug}`} className="whitespace-nowrap rounded-full px-3 py-1 text-muted hover:bg-bg hover:text-ink">
              {NICHE_EMOJI[n.slug] ?? "•"} {n.name}
            </Link>
          ))}
      </Container>
    </header>
  );
}

export function Footer({ brand, pages = [] }: { brand: string; pages?: PageLink[] }) {
  return (
    <footer className="mt-20 border-t border-border bg-surface">
      {pages.length > 0 && (
        <Container className="flex flex-wrap gap-x-6 gap-y-2 border-b border-border py-4 text-sm">
          {pages.map((p) => (
            <Link key={p.slug} href={`/pagina/${p.slug}`} className="text-muted hover:text-ink">
              {p.title}
            </Link>
          ))}
        </Container>
      )}
      <Container className="grid gap-6 py-10 text-sm text-muted sm:grid-cols-3">
        <div>
          <p className="font-heading text-base font-semibold text-ink">{brand}</p>
          <p className="mt-2">Peças impressas em 3D, feitas sob encomenda e personalizadas.</p>
        </div>
        <div className="space-y-1">
          <p className="font-medium text-ink">Compra segura</p>
          <p>Pix com desconto · acompanhamento do pedido em tempo real</p>
        </div>
        <div className="space-y-1">
          <p className="font-medium text-ink">Impressão 3D</p>
          <p>Linhas de camada podem ser visíveis: é a marca do processo, não um defeito.</p>
        </div>
      </Container>
    </footer>
  );
}

export function ProductTile({ product }: { product: ProductCard }) {
  return (
    <Link
      href={`/p/${product.slug}`}
      className="group flex flex-col overflow-hidden rounded-2xl border border-border bg-surface transition hover:-translate-y-0.5 hover:shadow-lg"
    >
      <div className="flex aspect-square items-center justify-center overflow-hidden bg-white text-6xl">
        {product.image ? (
          // eslint-disable-next-line @next/next/no-img-element -- miniatura WebP já otimizada pela API
          <img src={product.image} alt={product.title} loading="lazy" className="h-full w-full object-cover transition group-hover:scale-105" />
        ) : (
          <span className="transition group-hover:scale-110">{NICHE_EMOJI[product.niche] ?? "✨"}</span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1 p-4">
        <p className="line-clamp-2 text-sm font-medium">{product.title}</p>
        {product.customizable && <span className="w-fit rounded-full bg-secondary/15 px-2 py-0.5 text-xs text-secondary">personalizável</span>}
        <p className="mt-auto pt-2 font-heading text-lg font-bold text-primary">
          {product.price_from ? (
            <>
              <span className="text-xs font-normal text-muted">a partir de </span>
              {money(product.price_from)}
            </>
          ) : (
            <span className="text-sm font-normal text-muted">sob consulta</span>
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
    return <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{empty}</p>;
  }
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
      {products.map((p) => (
        <ProductTile key={p.slug} product={p} />
      ))}
    </div>
  );
}
