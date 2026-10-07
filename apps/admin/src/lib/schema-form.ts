/**
 * Converte o JSON Schema dos parâmetros (gerado pelo Pydantic na API) em campos de formulário.
 * Assim, parâmetro novo num modelo paramétrico aparece no painel sem mexer no frontend.
 */

type JsonSchema = {
  type?: string;
  enum?: (string | number)[];
  anyOf?: JsonSchema[];
  title?: string;
  description?: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  maxLength?: number;
};

export interface SchemaField {
  name: string;
  label: string;
  hint?: string;
  kind: "text" | "number" | "integer" | "boolean" | "enum";
  options: string[];
  nullable: boolean;
  min?: number;
  max?: number;
  maxLength?: number;
  defaultValue: unknown;
}

export function schemaFields(schema: { properties?: Record<string, JsonSchema> }): SchemaField[] {
  return Object.entries(schema.properties ?? {}).map(([name, prop]) => {
    const variants = prop.anyOf ?? [prop];
    const main = variants.find((v) => v.type !== "null") ?? prop;
    const nullable = variants.some((v) => v.type === "null");
    const kind: SchemaField["kind"] = main.enum
      ? "enum"
      : main.type === "boolean"
        ? "boolean"
        : main.type === "integer"
          ? "integer"
          : main.type === "number"
            ? "number"
            : "text";
    return {
      name,
      label: prop.title ?? name,
      hint: prop.description,
      kind,
      options: (main.enum ?? []).map(String),
      nullable,
      min: main.minimum,
      max: main.maximum,
      maxLength: main.maxLength,
      defaultValue: prop.default,
    };
  });
}

/** Valores do formulário → JSON dos parâmetros (números como número, vazio opcional = null). */
export function schemaPayload(fields: SchemaField[], form: FormData): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of fields) {
    if (f.kind === "boolean") {
      out[f.name] = form.get(f.name) === "on";
      continue;
    }
    const raw = String(form.get(f.name) ?? "").trim();
    if (raw === "") {
      if (f.nullable) out[f.name] = null;
      continue;
    }
    out[f.name] = f.kind === "number" || f.kind === "integer" ? Number(raw.replace(",", ".")) : raw;
  }
  return out;
}

export function optionLabel(value: string): string {
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
