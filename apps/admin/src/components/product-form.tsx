import type { Niche, ProductDetail } from "@/lib/types";
import { Button, Label, inputClass } from "./ui";

const ORIGINS = [
  ["parametrico", "Paramétrico próprio"],
  ["licenca_comercial", "Licença comercial comprada"],
  ["cc0", "CC0 (domínio público)"],
  ["cc_by", "CC BY (exige atribuição)"],
  ["outro", "Outra / não sei"],
] as const;
const MIN_MATERIALS = ["", "PLA", "PETG", "ASA", "TPU"] as const;

export function ProductForm({
  niches,
  product,
  action,
  submitLabel,
  id,
}: {
  niches: Niche[];
  product?: ProductDetail;
  action: (form: FormData) => Promise<void>;
  submitLabel: string;
  id?: string;
}) {
  const d = product?.design;
  return (
    <form id={id} action={action} className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <Label label="Título público *">
          <input name="title" required defaultValue={product?.title} className={inputClass} />
        </Label>
      </div>
      <Label label="Nicho *">
        <select name="niche" defaultValue={product?.niche} className={inputClass}>
          {niches.map((n) => (
            <option key={n.slug} value={n.slug}>
              {n.name}
            </option>
          ))}
        </select>
      </Label>
      <Label label="Categoria *" hint="ex.: nossa-senhora, cruzes, suportes">
        <input name="category" required defaultValue={product?.category} className={inputClass} />
      </Label>
      <Label label="Subcategoria" hint="ex.: aparecida">
        <input name="subcategory" defaultValue={product?.subcategory ?? ""} className={inputClass} />
      </Label>
      <Label label="Material mínimo" hint="ex.: ASA para peça de painel de carro">
        <select name="min_material" defaultValue={product?.min_material ?? ""} className={inputClass}>
          {MIN_MATERIALS.map((m) => (
            <option key={m} value={m}>
              {m || "nenhum"}
            </option>
          ))}
        </select>
      </Label>
      <div className="sm:col-span-2">
        <Label label="Descrição">
          <textarea name="description" rows={4} defaultValue={product?.description ?? ""} className={inputClass} />
        </Label>
      </div>
      <Label label="Tags" hint="separadas por vírgula">
        <input name="tags" defaultValue={product?.tags.join(", ")} className={inputClass} />
      </Label>
      <Label label="Ocasiões" hint="ex.: natal, batizado, dia das mães">
        <input name="occasions" defaultValue={product?.occasions.join(", ")} className={inputClass} />
      </Label>
      <label className="inline-flex items-center gap-2 text-sm sm:col-span-2">
        <input type="checkbox" name="customizable" defaultChecked={product?.customizable} className="accent-[var(--secondary)]" />
        Personalizável pelo cliente (nome, cor, tamanho)
      </label>

      <fieldset className="grid gap-4 rounded-xl border border-border p-4 sm:col-span-2 sm:grid-cols-2">
        <legend className="px-1 text-sm font-medium">Origem do modelo 3D e licença</legend>
        <Label label="Nome do design">
          <input name="design_name" defaultValue={d?.name} className={inputClass} />
        </Label>
        <Label label="Origem">
          <select name="origin" defaultValue={d?.origin ?? "parametrico"} className={inputClass}>
            {ORIGINS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Label>
        <Label label="Licença" hint="ex.: CC BY 4.0, licença comercial do pacote X">
          <input name="license" defaultValue={d?.license} className={inputClass} />
        </Label>
        <Label label="Autor">
          <input name="author" defaultValue={d?.author ?? ""} className={inputClass} />
        </Label>
        <Label label="Link de origem">
          <input name="source_url" defaultValue={d?.source_url ?? ""} className={inputClass} />
        </Label>
        <Label label="Texto de atribuição" hint="obrigatório para CC BY">
          <input name="attribution_text" defaultValue={d?.attribution_text ?? ""} className={inputClass} />
        </Label>
        <Label label="Personalizador 3D na loja" hint="liga o produto a um modelo paramétrico (prévia 3D para o cliente)">
          <select name="parametric_model" defaultValue={String(d?.params_schema?.model ?? "")} className={inputClass}>
            <option value="">nenhum</option>
            <option value="chaveiro-letra-nome">Chaveiro letra + nome</option>
            <option value="caixa">Caixa paramétrica</option>
          </select>
        </Label>
      </fieldset>

      <div className="sm:col-span-2">
        <Button type="submit">{submitLabel}</Button>
      </div>
    </form>
  );
}
