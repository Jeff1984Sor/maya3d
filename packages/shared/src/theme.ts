import type { BrandPublic } from "./brand";

/** Tokens permitidos (seção 5.1). Qualquer outra chave vinda do banco é descartada.
 * accent = detalhe da marca (ícone, letra destacada); soft = faixa de seção; deep = rodapé/faixa
 * escura (texto em cima dela usa a cor de fundo). */
export const TOKEN_NAMES = ["bg", "surface", "ink", "muted", "primary", "secondary", "border", "accent", "soft", "deep"] as const;

const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

function declarations(colors: Record<string, string>): string {
  return TOKEN_NAMES.flatMap((name) => {
    const value = colors[name];
    // Valida chave E valor: o resultado vai para uma tag <style>, então nada de CSS arbitrário.
    return value !== undefined && HEX.test(value) ? [`--${name}:${value};`] : [];
  }).join("");
}

/** CSS que sobrescreve os tokens padrão com a paleta da marca (claro + escuro). */
export function brandThemeCss(colors: BrandPublic["colors"]): string {
  const light = declarations(colors.light);
  const dark = declarations(colors.dark);
  return [
    light && `:root{${light}}`,
    dark && `@media (prefers-color-scheme:dark){:root{${dark}}}`,
  ]
    .filter(Boolean)
    .join("");
}

/** Paleta padrão (igual ao tokens.css), para quem não usa CSS — ex.: o app Expo. */
export const DEFAULT_TOKENS: Record<"light" | "dark", Record<(typeof TOKEN_NAMES)[number], string>> = {
  light: {
    bg: "#f7f4ef",
    surface: "#ffffff",
    ink: "#1e1e24",
    muted: "#6b7280",
    primary: "#ff6b2c",
    secondary: "#14b8a6",
    border: "#e7e2da",
    accent: "#ff6b2c",
    soft: "#efe9e1",
    deep: "#1e1e24",
  },
  dark: {
    bg: "#141418",
    surface: "#1e1e24",
    ink: "#f7f4ef",
    muted: "#9ca3af",
    primary: "#ff6b2c",
    secondary: "#14b8a6",
    border: "#2e2e36",
    accent: "#ff6b2c",
    soft: "#24242c",
    deep: "#0c0c0f",
  },
};

/** Paleta efetiva: padrão + cores válidas da marca (mesma validação de chave e hex). */
export function brandPalette(colors: BrandPublic["colors"], mode: "light" | "dark"): Record<(typeof TOKEN_NAMES)[number], string> {
  const out = { ...DEFAULT_TOKENS[mode] };
  for (const name of TOKEN_NAMES) {
    const value = colors[mode]?.[name];
    if (value !== undefined && HEX.test(value)) out[name] = value;
  }
  return out;
}

// --- Fontes da marca (Google Fonts) -----------------------------------------------------------
/** Nome de família aceito: letras, números e espaço (vai para URL e para CSS). */
const FONT_NAME = /^[A-Za-z0-9 ]{2,40}$/;
export const LOGO_TEXT_MODES = ["", "nome", "nome-destaque"] as const;

export interface BrandFonts {
  /** Folhas do Google Fonts a carregar (uma por família: se uma falhar, a outra segue). */
  hrefs: string[];
  /** CSS que troca as fontes de título e texto (só nomes validados). */
  css: string;
  /** Logo com o nome escrito ao lado: "nome" ou "nome-destaque" (minúsculo, última letra em destaque). */
  logoText: (typeof LOGO_TEXT_MODES)[number];
}

function family(name: string | undefined): string | null {
  const clean = name?.trim();
  return clean && FONT_NAME.test(clean) ? clean : null;
}

/** Fontes escolhidas no painel (Marca): título, texto e o modo do nome no logo. */
export function brandFonts(fonts: BrandPublic["fonts"]): BrandFonts {
  const heading = family(fonts.heading);
  const body = family(fonts.body);
  const hrefs = [heading, body]
    .filter((f, i, all): f is string => f !== null && all.indexOf(f) === i)
    .map((f) => `https://fonts.googleapis.com/css2?family=${f.replace(/ /g, "+")}:wght@400;600;700&display=swap`);
  const vars = [heading && `--f-heading:"${heading}";`, body && `--f-body:"${body}";`].filter(Boolean).join("");
  const mode = fonts.logo_texto ?? "";
  return {
    hrefs,
    // html:root vence a variável que o next/font põe na classe do <html>
    css: vars ? `html:root{${vars}}` : "",
    logoText: (LOGO_TEXT_MODES as readonly string[]).includes(mode) ? (mode as BrandFonts["logoText"]) : "",
  };
}
