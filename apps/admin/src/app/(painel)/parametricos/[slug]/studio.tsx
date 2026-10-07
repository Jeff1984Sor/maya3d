"use client";

import { useEffect, useState } from "react";
import { startGeneration } from "@/actions/parametric";
import { StlViewer } from "@/components/stl-viewer";
import { Alert, Badge, Button, Label, inputClass } from "@/components/ui";
import { optionLabel, schemaPayload, type SchemaField } from "@/lib/schema-form";

type Report = { bbox_mm: [number, number, number]; volume_mm3: number; watertight: boolean };
type Result = {
  files: Record<string, string>;
  combined: string;
  reports: Record<string, Report>;
  bbox_mm: [number, number, number];
  issues: string[];
  printable: boolean;
  prefix: string;
};
type JobState = { status: string; result?: Result; error?: string };

const POLL_MS = 1500;
const STATUS_LABEL: Record<string, string> = {
  enviando: "Enviando…",
  fila: "Na fila…",
  processando: "Gerando o modelo 3D…",
};

function FieldInput({ field }: { field: SchemaField }) {
  const value = field.defaultValue;
  const text = value === null || value === undefined ? "" : String(value);
  if (field.kind === "boolean") {
    return <input type="checkbox" name={field.name} defaultChecked={Boolean(value)} className="size-4 accent-[var(--secondary)]" />;
  }
  if (field.kind === "enum") {
    return (
      <select name={field.name} defaultValue={text} className={inputClass}>
        {field.nullable && <option value="">padrão</option>}
        {field.options.map((o) => (
          <option key={o} value={o}>
            {optionLabel(o)}
          </option>
        ))}
      </select>
    );
  }
  if (field.kind === "number" || field.kind === "integer") {
    return (
      <input
        name={field.name}
        type="number"
        step={field.kind === "integer" ? 1 : 0.1}
        min={field.min}
        max={field.max}
        defaultValue={text}
        className={inputClass}
      />
    );
  }
  return <input name={field.name} maxLength={field.maxLength} defaultValue={text} className={inputClass} />;
}

export function Studio({ slug, fields }: { slug: string; fields: SchemaField[] }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [state, setState] = useState<JobState | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    const tick = async () => {
      const res = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
      const data = (await res.json()) as JobState & { error?: string };
      if (stop) return;
      if (!res.ok) {
        setState({ status: "falhou", error: data.error ?? "falha ao consultar" });
        return;
      }
      setState(data);
      if (data.status === "fila" || data.status === "processando") setTimeout(tick, POLL_MS);
    };
    void tick();
    return () => {
      stop = true;
    };
  }, [jobId]);

  async function submit(form: FormData) {
    setState({ status: "enviando" });
    setJobId(null);
    const res = await startGeneration(slug, schemaPayload(fields, form));
    if (res.error || !res.jobId) setState({ status: "falhou", error: res.error });
    else setJobId(res.jobId);
  }

  const busy = state !== null && state.status in STATUS_LABEL;
  const result = state?.status === "concluido" ? state.result : undefined;

  return (
    <div className="grid gap-8 xl:grid-cols-2">
      <form action={submit} className="grid content-start gap-4 sm:grid-cols-2">
        {fields.map((f) => (
          <Label key={f.name} label={f.label} hint={f.hint}>
            <FieldInput field={f} />
          </Label>
        ))}
        <div className="sm:col-span-2">
          <Button type="submit" disabled={busy}>
            {busy ? STATUS_LABEL[state.status] : "Gerar peça"}
          </Button>
        </div>
      </form>

      <div className="space-y-4">
        {state?.status === "falhou" && <Alert tone="error">{state.error ?? "Falha na geração."}</Alert>}
        {busy && <p className="text-sm text-muted">{STATUS_LABEL[state.status]}</p>}
        {result && (
          <>
            <StlViewer url={`/api/files/${result.prefix}/${result.combined}`} />
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {result.printable ? <Badge tone="ok">imprimível</Badge> : <Badge tone="danger">precisa de ajuste</Badge>}
              <span className="text-muted">
                {result.bbox_mm.map((v) => v.toFixed(1)).join(" × ")} mm
              </span>
            </div>
            {result.issues.length > 0 && (
              <Alert tone="error">
                <ul className="list-inside list-disc">
                  {result.issues.map((i) => (
                    <li key={i}>{i}</li>
                  ))}
                </ul>
              </Alert>
            )}
            <div className="flex flex-wrap gap-3 text-sm">
              <a className="text-secondary hover:underline" href={`/api/files/${result.prefix}/${result.combined}`}>
                baixar STL completo
              </a>
              {Object.entries(result.files).map(([part, file]) => (
                <a key={part} className="text-secondary hover:underline" href={`/api/files/${result.prefix}/${file}`}>
                  {part} (cor separada)
                </a>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
