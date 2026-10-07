"use client";

import { useActionState } from "react";
import { runQuote, type ToolState } from "@/actions/tools";
import { Alert, Badge, Button, Label, inputClass } from "@/components/ui";
import { formatMoney } from "@/lib/form";
import type { Material, Printer, QuoteResponse } from "@/lib/types";

const COST_LABELS: Record<keyof QuoteResponse["cost"], string> = {
  material: "Material",
  energy: "Energia",
  wear: "Desgaste da máquina",
  labor: "Mão de obra",
  failure: "Taxa de falha",
  extras: "Embalagem e insumos",
  total: "Custo total",
};

export function QuoteForm({ materials, printers }: { materials: Material[]; printers: Printer[] }) {
  const [state, action, pending] = useActionState<ToolState<QuoteResponse>, FormData>(runQuote, {});

  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <form action={action} className="grid content-start gap-4 sm:grid-cols-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="grid grid-cols-[1fr_7rem] gap-2 sm:col-span-2">
            <Label label={i === 1 ? "Material (cor 1) *" : `Material (cor ${i})`}>
              <select name={`material_${i}`} className={inputClass} defaultValue={i === 1 ? String(materials[0]?.id) : ""}>
                {i > 1 && <option value="">—</option>}
                {materials.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.kind} {m.color_name}
                  </option>
                ))}
              </select>
            </Label>
            <Label label="Gramas">
              <input name={`grams_${i}`} inputMode="decimal" required={i === 1} className={inputClass} />
            </Label>
          </div>
        ))}
        <Label label="Impressora *">
          <select name="printer_id" className={inputClass}>
            {printers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.status})
              </option>
            ))}
          </select>
        </Label>
        <Label label="Tempo de impressão (horas) *" hint="ex.: 2,5">
          <input name="print_hours" inputMode="decimal" required className={inputClass} />
        </Label>
        <Label label="Pós-processamento (min)">
          <input name="post_minutes" type="number" min={0} defaultValue={0} className={inputClass} />
        </Label>
        <Label label="Embalagem e insumos (R$)" hint="caixa, argola, ímã…">
          <input name="extra_costs" inputMode="decimal" defaultValue="0" className={inputClass} />
        </Label>
        <Label label="Categoria" hint="usa a margem da categoria, se houver">
          <input name="category" className={inputClass} />
        </Label>
        <Label label="Canais" hint="vazio = todos com tarifa cadastrada; separados por vírgula">
          <input name="channels" className={inputClass} />
        </Label>
        <Label label="Frete assumido (R$)" hint="aplicado aos canais listados">
          <input name="shipping" inputMode="decimal" className={inputClass} />
        </Label>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={pending}>
            {pending ? "Calculando…" : "Calcular"}
          </Button>
        </div>
      </form>

      <div className="space-y-4">
        {state.error && <Alert tone="error">{state.error}</Alert>}
        {state.result && <QuoteResult result={state.result} />}
      </div>
    </div>
  );
}

function QuoteResult({ result }: { result: QuoteResponse }) {
  return (
    <>
      {result.warnings.map((w) => (
        <Alert key={w} tone="error">
          {w}
        </Alert>
      ))}
      <div className="rounded-xl border border-border">
        <table className="w-full text-sm">
          <tbody>
            {(Object.keys(COST_LABELS) as (keyof QuoteResponse["cost"])[]).map((k) => (
              <tr key={k} className={k === "total" ? "font-semibold" : "text-muted"}>
                <td className="px-4 py-1.5">{COST_LABELS[k]}</td>
                <td className="px-4 py-1.5 text-right">{formatMoney(result.cost[k])}</td>
              </tr>
            ))}
            <tr>
              <td className="px-4 py-1.5 text-muted">Lucro alvo</td>
              <td className="px-4 py-1.5 text-right">{formatMoney(result.target_profit)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="text-xs uppercase text-muted">
            <tr>
              <th className="px-3 py-2 text-left">Canal</th>
              <th className="px-3 py-2 text-right">Preço</th>
              <th className="px-3 py-2 text-right">Tarifas</th>
              <th className="px-3 py-2 text-right">Lucro</th>
            </tr>
          </thead>
          <tbody>
            {result.quotes.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-center text-muted">
                  Nenhum canal com tarifa cadastrada.
                </td>
              </tr>
            )}
            {result.quotes.map((q) =>
              q.error ? (
                <tr key={q.channel} className="border-t border-border">
                  <td className="px-3 py-2">{q.channel}</td>
                  <td colSpan={3} className="px-3 py-2 text-right">
                    <Badge tone="danger">{q.error}</Badge>
                  </td>
                </tr>
              ) : (
                <tr key={q.channel} className="border-t border-border">
                  <td className="px-3 py-2">{q.channel}</td>
                  <td className="px-3 py-2 text-right font-semibold text-primary">{formatMoney(q.price)}</td>
                  <td className="px-3 py-2 text-right text-muted">
                    {formatMoney(Number(q.commission) + Number(q.fixed_fee) + Number(q.shipping))}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {formatMoney(q.net_profit)} <span className="text-xs text-muted">({q.margin_pct}%)</span>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
