import type { BrandPublic } from "./brand";

/** Tokens permitidos (seção 5.1). Qualquer outra chave vinda do banco é descartada. */
export const TOKEN_NAMES = ["bg", "surface", "ink", "muted", "primary", "secondary", "border"] as const;

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
  light: { bg: "#f7f4ef", surface: "#ffffff", ink: "#1e1e24", muted: "#6b7280", primary: "#ff6b2c", secondary: "#14b8a6", border: "#e7e2da" },
  dark: { bg: "#141418", surface: "#1e1e24", ink: "#f7f4ef", muted: "#9ca3af", primary: "#ff6b2c", secondary: "#14b8a6", border: "#2e2e36" },
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
