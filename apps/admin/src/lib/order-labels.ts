/** Rótulos dos status de pedido no painel (espelham print3d_core.orders). */
export const STATUS_LABEL: Record<string, string> = {
  aguardando_pagamento: "Aguardando pagamento",
  pago: "Pago",
  imprimindo_amostra: "Imprimindo amostra",
  amostra_pronta: "Amostra pronta",
  ajuste_solicitado: "Ajuste solicitado",
  na_fila: "Na fila",
  imprimindo: "Imprimindo",
  acabamento: "Acabamento",
  embalado: "Embalado",
  saiu_para_entrega: "Saiu para entrega",
  enviado: "Enviado",
  entregue: "Entregue",
  cancelado: "Cancelado",
};

export const ACTIVE_STATUSES = [
  "aguardando_pagamento",
  "pago",
  "imprimindo_amostra",
  "amostra_pronta",
  "ajuste_solicitado",
  "na_fila",
  "imprimindo",
  "acabamento",
  "embalado",
  "saiu_para_entrega",
  "enviado",
];

export function statusTone(status: string): "ok" | "danger" | "warn" | "muted" {
  if (status === "entregue") return "ok";
  if (status === "cancelado") return "danger";
  if (status.includes("amostra") || status === "ajuste_solicitado" || status === "aguardando_pagamento") return "warn";
  return "muted";
}

export const label = (status: string) => STATUS_LABEL[status] ?? status;
