import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import { brandThemeCss } from "@print3d/shared";
import { api } from "@/lib/api";
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
  const brand = await api.getBrandOrFallback();
  return (
    <html lang="pt-BR" className={`${heading.variable} ${body.variable}`}>
      <head>
        {/* brandThemeCss só emite hex validado: seguro para <style> */}
        <style dangerouslySetInnerHTML={{ __html: brandThemeCss(brand.colors) }} />
      </head>
      <body className="min-h-dvh font-sans antialiased">{children}</body>
    </html>
  );
}
