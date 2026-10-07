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
