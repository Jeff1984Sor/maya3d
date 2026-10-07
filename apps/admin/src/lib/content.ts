/** Campos da marca editáveis no painel (mesmos tokens validados pela API e pela loja). */
export const TOKENS = ["bg", "surface", "ink", "muted", "primary", "secondary", "border"] as const;
export const TOKEN_LABELS: Record<(typeof TOKENS)[number], string> = {
  bg: "Fundo",
  surface: "Cartões",
  ink: "Texto",
  muted: "Texto suave",
  primary: "Principal (botões, preço)",
  secondary: "Destaque (links)",
  border: "Bordas",
};
export const SOCIALS = ["instagram", "facebook", "tiktok", "youtube", "pinterest"] as const;
export const SECTION_KINDS = [
  { id: "newest", label: "Novidades (mais recentes)", hint: "" },
  { id: "niche", label: "Por tema (nicho)", hint: "slug do nicho, ex.: religioso" },
  { id: "category", label: "Por categoria", hint: "ex.: tercos" },
  { id: "tag", label: "Por tag", hint: "ex.: batizado" },
  { id: "manual", label: "Escolhidos a dedo", hint: "endereços dos produtos separados por vírgula" },
] as const;
