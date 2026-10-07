"use client";

import { useActionState } from "react";
import { runGuardian, type ToolState } from "@/actions/tools";
import { Alert, Badge, Button, Label, inputClass } from "@/components/ui";
import type { GuardianResult, Niche } from "@/lib/types";

const ORIGINS = [
  ["parametrico", "Paramétrico próprio"],
  ["licenca_comercial", "Licença comercial comprada"],
  ["cc0", "CC0"],
  ["cc_by", "CC BY"],
  ["outro", "Outra / não sei"],
] as const;
const KINDS = ["PLA", "PETG", "ASA", "TPU"] as const;

export function GuardianForm({ niches }: { niches: Niche[] }) {
  const [state, action, pending] = useActionState<ToolState<GuardianResult>, FormData>(runGuardian, {});

  return (
    <div className="grid gap-8 xl:grid-cols-2">
      <form action={action} className="grid content-start gap-4 sm:grid-cols-2">
        <Label label="Nicho *">
          <select name="niche" className={inputClass}>
            {niches.map((n) => (
              <option key={n.slug} value={n.slug}>
                {n.name}
              </option>
            ))}
          </select>
        </Label>
        <Label label="Canal" hint="para conferir licenças por canal">
          <select name="channel" className={inputClass} defaultValue="">
            <option value="">qualquer</option>
            <option value="site">site</option>
            <option value="mercadolivre">mercadolivre</option>
            <option value="shopee">shopee</option>
          </select>
        </Label>
        <div className="sm:col-span-2">
          <Label label="Título *">
            <input name="title" required className={inputClass} placeholder="ex.: Porta-vela Nossa Senhora" />
          </Label>
        </div>
        <div className="sm:col-span-2">
          <Label label="Descrição">
            <textarea name="description" rows={3} className={inputClass} />
          </Label>
        </div>
        <Label label="Tags" hint="separadas por vírgula">
          <input name="tags" className={inputClass} />
        </Label>
        <Label label="Ocasiões" hint="ex.: natal, dia das criancas">
          <input name="occasions" className={inputClass} />
        </Label>
        <Label label="Origem do modelo">
          <select name="origin" className={inputClass} defaultValue="parametrico">
            {ORIGINS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Label>
        <Label label="Licença" hint="ex.: CC BY 4.0">
          <input name="license" className={inputClass} />
        </Label>
        <Label label="Autor (atribuição)">
          <input name="author" className={inputClass} />
        </Label>
        <Label label="Texto do cliente" hint="nome do chaveiro, frase da placa…">
          <input name="customer_text" className={inputClass} />
        </Label>
        <div className="sm:col-span-2">
          <span className="text-sm font-medium">Materiais</span>
          <div className="mt-1 flex gap-4">
            {KINDS.map((k) => (
              <label key={k} className="inline-flex items-center gap-1.5 text-sm">
                <input type="checkbox" name="material_kinds" value={k} className="accent-[var(--secondary)]" />
                {k}
              </label>
            ))}
          </div>
        </div>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={pending}>
            {pending ? "Verificando…" : "Verificar"}
          </Button>
        </div>
      </form>

      <div className="space-y-4">
        {state.error && <Alert tone="error">{state.error}</Alert>}
        {state.result && <Verdict result={state.result} />}
      </div>
    </div>
  );
}

function Verdict({ result }: { result: GuardianResult }) {
  return (
    <div className="space-y-4">
      <div
        className={`rounded-2xl border p-5 ${result.approved ? "border-secondary/50 bg-secondary/10" : "border-primary/50 bg-primary/10"}`}
      >
        <p className="font-heading text-xl font-bold">{result.approved ? "Aprovado" : "Bloqueado"}</p>
        <p className="text-xs text-muted">registro #{result.audit_id} na auditoria</p>
      </div>

      {result.violations.length > 0 && (
        <ul className="space-y-2">
          {result.violations.map((v) => (
            <li key={v.code + v.evidence} className="rounded-xl border border-border p-3 text-sm">
              <Badge tone="danger">{v.code}</Badge> <span className="ml-1">{v.message}</span>
              {v.evidence && <span className="mt-1 block text-xs text-muted">encontrado: “{v.evidence}”</span>}
            </li>
          ))}
        </ul>
      )}

      {(result.disclaimers.length > 0 || result.age_rating || result.attribution_required) && (
        <div className="rounded-xl border border-border p-3 text-sm">
          <p className="mb-2 font-medium">O anúncio precisa ter</p>
          <ul className="list-inside list-disc space-y-1 text-muted">
            {result.age_rating && <li>Classificação {result.age_rating} / colecionável / decoração</li>}
            {result.attribution_required && <li>Atribuição ao autor (licença CC BY)</li>}
            {result.disclaimers.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </div>
      )}

      {result.warnings.map((w) => (
        <p key={w} className="text-xs text-muted">
          {w}
        </p>
      ))}
    </div>
  );
}
