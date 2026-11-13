export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : "—";
}

export const NICHE_EMOJI: Record<string, string> = {
  religioso: "✝️",
  automotivo: "🚗",
  celular: "📱",
  brindes: "🎁",
  "datas-comemorativas": "🎉",
  fitness: "💪",
  chaveiros: "🔑",
  infantil: "🐶",
  caixas: "📦",
  "casa-e-decoracao": "🏠",
};

/** Nome bonito da categoria (vem como identificador: "dia-das-maes"). */
const CATEGORY_LABELS: Record<string, string> = {
  natal: "Natal",
  pascoa: "Páscoa",
  "dia-das-maes": "Dia das Mães",
  "dia-dos-pais": "Dia dos Pais",
  "dia-dos-namorados": "Dia dos Namorados",
  "dia-das-criancas": "Dia das Crianças",
  aniversario: "Aniversário",
  "casa-e-decoracao": "Casa e decoração",
  "presepios-e-natal": "Presépios e Natal",
  "jesus-e-paixao": "Jesus e Paixão",
  "estatuas-e-devocao": "Estátuas e devoção",
  "decoracao-e-placas": "Decoração e placas",
  "acessorios-e-lembrancinhas": "Acessórios e lembrancinhas",
  "infantil-e-batizado": "Infantil e batizado",
  "cruzes-e-crucifixos": "Cruzes e crucifixos",
  "stl-dos-anuncios": "Destaques",
};

export function categoryLabel(slug: string): string {
  if (CATEGORY_LABELS[slug]) return CATEGORY_LABELS[slug];
  const text = slug.replace(/-/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
