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
};
