import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import { brandFonts, brandThemeCss } from "@print3d/shared";
import { currentCart } from "@/actions/cart";
import { Assistant } from "@/components/assistant";
import { Announcement, Footer, Header, WhatsAppButton } from "@/components/shop";
import { api } from "@/lib/api";
import { storeApiOrNull, type Home, type Niche, type PageLink, type StoreSettings } from "@/lib/store";
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
  const [brand, niches, settings, cart, pages, home] = await Promise.all([
    api.getBrandOrFallback(),
    storeApiOrNull<Niche[]>("/niches", 60),
    storeApiOrNull<StoreSettings>("/settings", 60),
    currentCart(),
    storeApiOrNull<PageLink[]>("/pages", 60),
    storeApiOrNull<Home>("/home", 60),
  ]);
  const cartCount = cart?.items.reduce((n, i) => n + i.quantity, 0) ?? 0;
  const fonts = brandFonts(brand.fonts);
  return (
    <html lang="pt-BR" className={`${heading.variable} ${body.variable}`}>
      <head>
        {/* brandThemeCss/brandFonts só emitem hex e nomes de fonte validados: seguro para <style> */}
        <style dangerouslySetInnerHTML={{ __html: brandThemeCss(brand.colors) + fonts.css }} />
        {fonts.hrefs.length > 0 && (
          <>
            <link rel="preconnect" href="https://fonts.googleapis.com" />
            <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
            {fonts.hrefs.map((href) => (
              <link key={href} rel="stylesheet" href={href} />
            ))}
          </>
        )}
      </head>
      <body className="flex min-h-dvh flex-col font-sans antialiased">
        <Announcement freeMin={settings?.free_shipping_min ?? null} text={home?.announcement} />
        <Header brand={brand.name} logo={brand.logo_light_url} logoText={fonts.logoText} niches={niches ?? []} cartCount={cartCount} />
        <main className="flex-1">{children}</main>
        <Footer brand={brand.name} logo={brand.logo_dark_url ?? brand.logo_light_url} logoText={fonts.logoText} tagline={brand.tagline} pages={pages ?? []} email={brand.contact_email} whatsapp={brand.contact_whatsapp} social={brand.social} />
        {brand.contact_whatsapp && <WhatsAppButton phone={brand.contact_whatsapp} raised={Boolean(settings?.assistant_enabled)} />}
        {settings?.assistant_enabled && <Assistant brand={brand.name} />}
      </body>
    </html>
  );
}
