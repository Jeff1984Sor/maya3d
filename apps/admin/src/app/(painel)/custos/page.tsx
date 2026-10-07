import type { Metadata } from "next";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { Flash } from "@/components/flash";
import { Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";
import type { CostConfig } from "@/lib/types";

export const metadata: Metadata = { title: "Custos" };

const FIELDS = [
  { name: "energy_price_kwh", label: "Tarifa de energia (R$/kWh)" },
  { name: "labor_per_hour", label: "Mão de obra (R$/hora)" },
  { name: "failure_rate", label: "Taxa de falha", hint: "0.10 = 10% das impressões perdidas" },
  { name: "min_profit", label: "Lucro mínimo por peça (R$)" },
  { name: "default_margin", label: "Margem padrão sobre o custo", hint: "0.40 = 40%" },
] as const;

function parseMargins(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const [category, value] = line.split("=").map((s) => s.trim());
    if (category && value) out[category] = value.replace(",", ".");
  }
  return out;
}

async function save(form: FormData): Promise<void> {
  "use server";
  await requireSession();
  const payload: Record<string, unknown> = { margin_by_category: parseMargins(String(form.get("margins") ?? "")) };
  for (const f of FIELDS) payload[f.name] = String(form.get(f.name) ?? "").replace(",", ".");
  try {
    await api.put("/cost-config", payload);
  } catch (error) {
    const msg = error instanceof AdminApiError ? error.message : "Falha ao salvar.";
    redirect(`/custos?erro=${encodeURIComponent(msg)}`);
  }
  revalidatePath("/custos");
  redirect(`/custos?ok=${encodeURIComponent("Custos salvos. Preços passam a usar os novos valores.")}`);
}

export default async function CustosPage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const config = await api.get<CostConfig>("/cost-config");
  const margins = Object.entries(config.margin_by_category)
    .map(([k, v]) => `${k}=${v}`)
    .join("\n");

  return (
    <>
      <PageHeader
        title="Custos"
        description="Base de todo preço. Mudanças aqui ficam registradas na auditoria e, a partir da Fase 3, ressincronizam os anúncios."
      />
      <Flash {...await searchParams} />
      <Card>
        <form action={save} className="grid gap-4 sm:grid-cols-2">
          {FIELDS.map((f) => (
            <Label key={f.name} label={f.label} hint={"hint" in f ? f.hint : undefined}>
              <input name={f.name} required inputMode="decimal" defaultValue={config[f.name]} className={inputClass} />
            </Label>
          ))}
          <div className="sm:col-span-2">
            <Label label="Margem por categoria" hint="uma por linha: categoria=0.45 (sobrescreve a margem padrão)">
              <textarea name="margins" rows={4} defaultValue={margins} className={inputClass} />
            </Label>
          </div>
          <div className="sm:col-span-2 flex items-center justify-between">
            <Button type="submit">Salvar</Button>
            <span className="text-xs text-muted">Atualizado em {new Date(config.updated_at).toLocaleString("pt-BR")}</span>
          </div>
        </form>
      </Card>
    </>
  );
}
