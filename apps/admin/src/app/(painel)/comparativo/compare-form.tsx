"use client";

import { useActionState } from "react";
import { runCompare, type CompareResult, type ToolState } from "@/actions/tools";
import { Alert, Badge, Button, Label, inputClass } from "@/components/ui";
import { formatMoney } from "@/lib/form";
import type { Material, Printer } from "@/lib/types";

type Prefill = { ref?: string; grams?: string; hours?: string; post?: string; category?: string };

export function CompareForm({ materials, printers, prefill }: { materials: Material[]; printers: Printer[]; prefill: Prefill }) {
  const [state, action, pending] = useActionState<ToolState<CompareResult>, FormData>(runCompare, {});
  const result = state.result;
  const channels = result ? [...new Set(result.rows.flatMap((r) => r.quotes.map((q) => q.channel)))] : [];
  const cheapest = result?.rows[0]?.cost.total;

  return (
    <div className="space-y-8">
      <form action={action} className="grid gap-4 sm:grid-cols-3">
        <Label label="Peça de referência: material *" hint="o material em que você sabe as gramas">
          <select name="reference_material_id" defaultValue={prefill.ref ?? String(materials[0]?.id)} className={inputClass}>
            {materials.map((m) => (
              <option key={m.id} value={m.id}>
                {m.kind} {m.color_name}
              </option>
            ))}
          </select>
        </Label>
        <Label label="Gramas nesse material *">
          <input name="grams" required inputMode="decimal" defaultValue={prefill.grams} className={inputClass} />
        </Label>
        <Label label="Tempo de impressão (h) *">
          <input name="print_hours" required inputMode="decimal" defaultValue={prefill.hours} className={inputClass} />
        </Label>
        <Label label="Impressora *">
          <select name="printer_id" className={inputClass}>
            {printers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.status})
              </option>
            ))}
          </select>
        </Label>
        <Label label="Pós-processamento (min)">
          <input name="post_minutes" type="number" min={0} defaultValue={prefill.post ?? 0} className={inputClass} />
        </Label>
        <Label label="Embalagem e insumos (R$)">
          <input name="extra_costs" inputMode="decimal" defaultValue="0" className={inputClass} />
        </Label>
        <Label label="Categoria" hint="usa a margem da categoria">
          <input name="category" defaultValue={prefill.category} className={inputClass} />
        </Label>
        <Label label="Canais" hint="vazio = todos com tarifa">
          <input name="channels" className={inputClass} />
        </Label>
        <div className="flex items-end">
          <Button type="submit" disabled={pending}>
            {pending ? "Comparando…" : "Comparar materiais"}
          </Button>
        </div>
      </form>

      {state.error && <Alert tone="error">{state.error}</Alert>}

      {result && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-3 py-2 text-left">Material</th>
                <th className="px-3 py-2 text-right">Gramas</th>
                <th className="px-3 py-2 text-right">Material</th>
                <th className="px-3 py-2 text-right">Custo total</th>
                {channels.map((c) => (
                  <th key={c} className="px-3 py-2 text-right">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((r) => (
                <tr key={r.material_id} className="border-b border-border align-top last:border-0">
                  <td className="px-3 py-2">
                    <span className="mr-2 inline-block size-3 rounded-full border border-border align-middle" style={{ background: r.color_hex }} />
                    {r.label}
                    {r.cost.total === cheapest && <Badge tone="ok">mais barato</Badge>}
                    {r.warnings.map((w) => (
                      <span key={w} className="block text-xs text-primary">
                        {w}
                      </span>
                    ))}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {Number(r.grams).toLocaleString("pt-BR")} g
                    <span className="block text-xs text-muted">{Number(r.density).toLocaleString("pt-BR")} g/cm³</span>
                  </td>
                  <td className="px-3 py-2 text-right text-muted">{formatMoney(r.cost.material)}</td>
                  <td className="px-3 py-2 text-right font-semibold">{formatMoney(r.cost.total)}</td>
                  {channels.map((c) => {
                    const q = r.quotes.find((x) => x.channel === c);
                    return (
                      <td key={c} className="px-3 py-2 text-right">
                        {q?.price ? (
                          <>
                            <span className="font-semibold text-primary">{formatMoney(q.price)}</span>
                            <span className="block text-xs text-muted">lucro {formatMoney(q.net_profit)}</span>
                          </>
                        ) : (
                          <span className="text-xs text-muted">{q?.error ?? "—"}</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-3 py-2 text-xs text-muted">
            Referência: {Number(result.reference_grams).toLocaleString("pt-BR")} g de {result.reference}. O tempo de impressão foi mantido igual
            (aproximação); com o fatiador, cada material terá o tempo real.
          </p>
        </div>
      )}
    </div>
  );
}
