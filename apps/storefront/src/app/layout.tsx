import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import { brandThemeCss } from "@print3d/shared";
import { currentCart } from "@/actions/cart";
import { Announcement, Footer, Header } from "@/components/shop";
import { api } from "@/lib/api";
import { storeApiOrNull, type Niche, type StoreSettings } from "@/lib/store";
import "./globals.css";

const heading = Space_Grotesk({ subsets: ["latin"], variable: "--f-heading" });
const body = Inter({ subsets: ["latin"], variable: "--f-body" });

export async function generateMetadata(): Promise<Metadata> {
  const brand = await api.getBrandOrFallback();
  return {
    title: { default: brand.name, template: `%s · ${brand.name}` },
    description: brand.tagline ?? undefined,
    icons: brand.favicon_url ? { icon: brand.favicon_url } : undefined,
  };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [brand, niches, settings, cart] = await Promise.all([
    api.getBrandOrFallback(),
    storeApiOrNull<Niche[]>("/niches", 60),
    storeApiOrNull<StoreSettings>("/settings", 60),
    currentCart(),
  ]);
  const cartCount = cart?.items.reduce((n, i) => n + i.quantity, 0) ?? 0;
  return (
    <html lang="pt-BR" className={`${heading.variable} ${body.variable}`}>
      <head>
        {/* brandThemeCss só emite hex validado: seguro para <style> */}
        <style dangerouslySetInnerHTML={{ __html: brandThemeCss(brand.colors) }} />
      </head>
      <body className="flex min-h-dvh flex-col font-sans antialiased">
        <Announcement freeMin={settings?.free_shipping_min ?? null} />
        <Header brand={brand.name} niches={niches ?? []} cartCount={cartCount} />
        <main className="flex-1">{children}</main>
        <Footer brand={brand.name} />
      </body>
    </html>
  );
}
