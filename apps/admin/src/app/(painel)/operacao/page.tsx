import type { Metadata } from "next";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { Flash } from "@/components/flash";
import { Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

export const metadata: Metadata = { title: "Operação" };

type Ops = {
  sample_threshold: number;
  free_sample_rounds: number;
  sample_reminder_hours: number[];
  local_free_shipping_min: string;
  local_cities_ibge: string[];
  local_delivery_fee: string;
  pickup_enabled: boolean;
  owner_whatsapp: string | null;
  pix_key: string | null;
  pix_name: string | null;
  origin_cep: string | null;
};

const nums = (v: FormDataEntryValue | null) =>
  String(v ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

async function save(form: FormData): Promise<void> {
  "use server";
  await requireSession();
  try {
    await api.put("/ops-config", {
      sample_threshold: Number(form.get("sample_threshold")),
      free_sample_rounds: Number(form.get("free_sample_rounds")),
      sample_reminder_hours: nums(form.get("sample_reminder_hours")).map(Number),
      local_free_shipping_min: String(form.get("local_free_shipping_min")).replace(",", "."),
      local_cities_ibge: nums(form.get("local_cities_ibge")),
      local_delivery_fee: String(form.get("local_delivery_fee")).replace(",", "."),
      pickup_enabled: form.get("pickup_enabled") === "on",
      owner_whatsapp: String(form.get("owner_whatsapp") ?? "").trim() || null,
      pix_key: String(form.get("pix_key") ?? "").trim() || null,
      pix_name: String(form.get("pix_name") ?? "").trim() || null,
      origin_cep: String(form.get("origin_cep") ?? "").replace(/\D/g, "") || null,
    });
  } catch (error) {
    redirect(`/operacao?erro=${encodeURIComponent(error instanceof AdminApiError ? error.message : "Falha ao salvar.")}`);
  }
  revalidatePath("/operacao");
  redirect(`/operacao?ok=${encodeURIComponent("Regras de operação salvas.")}`);
}

export default async function OperacaoPage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const ops = await api.get<Ops>("/ops-config");
  return (
    <>
      <PageHeader title="Operação" description="Amostra em pedidos grandes, entrega local e o seu WhatsApp para avisos de venda." />
      <Flash {...await searchParams} />
      <Card>
        <form action={save} className="grid gap-4 sm:grid-cols-2">
          <Label label="Amostra quando a quantidade passar de" hint="spec: 10 unidades">
            <input name="sample_threshold" type="number" min={1} defaultValue={ops.sample_threshold} className={inputClass} />
          </Label>
          <Label label="Rodadas de ajuste grátis" hint="acima disso, cobrar taxa de amostra">
            <input name="free_sample_rounds" type="number" min={0} defaultValue={ops.free_sample_rounds} className={inputClass} />
          </Label>
          <Label label="Lembretes de amostra (horas)" hint="ex.: 24, 48">
            <input name="sample_reminder_hours" defaultValue={ops.sample_reminder_hours.join(", ")} className={inputClass} />
          </Label>
          <Label label="Seu WhatsApp (avisos de venda)" hint="+5515999999999">
            <input name="owner_whatsapp" defaultValue={ops.owner_whatsapp ?? ""} className={inputClass} />
          </Label>
          <Label label="Chave Pix da loja" hint="aparece para o cliente no checkout (Pix manual até o gateway)">
            <input name="pix_key" defaultValue={ops.pix_key ?? ""} className={inputClass} />
          </Label>
          <Label label="Nome do recebedor do Pix">
            <input name="pix_name" defaultValue={ops.pix_name ?? ""} className={inputClass} />
          </Label>
          <Label label="CEP de onde saem os envios" hint="usado na cotação automática de frete (Melhor Envio)">
            <input name="origin_cep" inputMode="numeric" maxLength={9} defaultValue={ops.origin_cep ?? ""} className={inputClass} />
          </Label>
          <Label label="Frete grátis local a partir de (R$)">
            <input name="local_free_shipping_min" inputMode="decimal" defaultValue={ops.local_free_shipping_min} className={inputClass} />
          </Label>
          <Label label="Taxa de entrega local abaixo do mínimo (R$)">
            <input name="local_delivery_fee" inputMode="decimal" defaultValue={ops.local_delivery_fee} className={inputClass} />
          </Label>
          <Label label="Cidades atendidas (código IBGE)" hint="Sorocaba = 3552205; separe por vírgula">
            <input name="local_cities_ibge" defaultValue={ops.local_cities_ibge.join(", ")} className={inputClass} />
          </Label>
          <label className="inline-flex items-center gap-2 self-end pb-2 text-sm">
            <input type="checkbox" name="pickup_enabled" defaultChecked={ops.pickup_enabled} className="accent-[var(--secondary)]" />
            Permitir retirada sem custo
          </label>
          <div className="sm:col-span-2">
            <Button type="submit">Salvar</Button>
          </div>
        </form>
      </Card>
    </>
  );
}
