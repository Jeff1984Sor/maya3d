import type { Field } from "./resources";

type Json = string | number | boolean | null | string[];

/**
 * FormData → JSON no formato da API. Valores monetários/decimais vão como string
 * (a API usa Decimal; nada de float arredondando centavos).
 * `mode: "create"` omite opcionais vazios; `"update"` manda null para limpar e ignora createOnly.
 */
export function formToPayload(
  fields: readonly Field[],
  form: FormData,
  mode: "create" | "update",
): Record<string, Json> {
  const out: Record<string, Json> = {};
  for (const field of fields) {
    if (mode === "update" && field.createOnly) continue;

    if (field.type === "checkbox") {
      out[field.name] = form.get(field.name) === "on";
      continue;
    }
    if (field.type === "checkboxes") {
      out[field.name] = form.getAll(field.name).map(String);
      continue;
    }

    const raw = String(form.get(field.name) ?? "").trim();
    if (field.type === "list") {
      out[field.name] = raw ? raw.split(",").map((s) => s.trim()).filter(Boolean) : [];
      continue;
    }
    if (raw === "") {
      if (mode === "update" && !field.required) out[field.name] = null;
      continue;
    }
    switch (field.type) {
      case "int":
        out[field.name] = Number.parseInt(raw, 10);
        break;
      case "money":
      case "decimal":
        out[field.name] = raw.replace(",", ".");
        break;
      default:
        out[field.name] = raw;
    }
  }
  return out;
}

export function formatMoney(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : "—";
}

export function formatPercent(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  return Number.isFinite(n) ? `${(n * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%` : "—";
}
