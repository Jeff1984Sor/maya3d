/** Espelha `BrandPublic` da API. Fonte da verdade: tabela `brand_settings`. */
export interface BrandPublic {
  name: string;
  tagline: string | null;
  logo_light_url: string | null;
  logo_dark_url: string | null;
  favicon_url: string | null;
  colors: { light: Record<string, string>; dark: Record<string, string> };
  fonts: Record<string, string>;
  domain: string | null;
  contact_email: string | null;
  contact_whatsapp: string | null;
  social: Record<string, string>;
}

/**
 * Usada só quando a API está fora do ar, para a página nunca quebrar.
 * Nome neutro de propósito: a marca real vem do banco (spec 0.1).
 */
export const FALLBACK_BRAND: BrandPublic = {
  name: "Print3D",
  tagline: null,
  logo_light_url: null,
  logo_dark_url: null,
  favicon_url: null,
  colors: { light: {}, dark: {} }, // vazio => vale o tokens.css padrão
  fonts: {},
  domain: null,
  contact_email: null,
  contact_whatsapp: null,
  social: {},
};
