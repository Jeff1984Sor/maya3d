"use client";

import { useEffect, useState, useTransition } from "react";
import { startPhoto } from "@/actions/photo";
import { StlViewer } from "@/components/stl-viewer";
import { Alert, Badge, Button, Label, inputClass } from "@/components/ui";

type Mode = "litofania" | "placa_multicor" | "cortador" | "chaveiro_silhueta";
type Field = { name: string; label: string; value: string; hint?: string };

const MODES: { key: Mode; title: string; text: string; fields: Field[]; invert?: boolean }[] = [
  {
    key: "litofania",
    title: "Litofania",
    text: "Contra a luz, a foto aparece. Ótima para presentes (mães, namorados, bebê).",
    fields: [
      { name: "width_mm", label: "Largura (mm)", value: "100" },
      { name: "min_mm", label: "Espessura mínima (mm)", value: "0.8", hint: "partes claras" },
      { name: "max_mm", label: "Espessura máxima (mm)", value: "3.0", hint: "partes escuras" },
      { name: "frame_mm", label: "Moldura (mm)", value: "3", hint: "0 = sem moldura" },
    ],
  },
  {
    key: "placa_multicor",
    title: "Placa multicor",
    text: "A imagem vira 2–4 cores em camadas. Com AMS ou trocando o filamento nas alturas indicadas.",
    fields: [
      { name: "width_mm", label: "Largura (mm)", value: "100" },
      { name: "colors", label: "Número de cores", value: "4", hint: "2 a 4" },
    ],
  },
  {
    key: "cortador",
    title: "Cortador de biscoito",
    text: "Use um desenho escuro sobre fundo claro (ou marque inverter).",
    fields: [
      { name: "size_mm", label: "Tamanho (mm)", value: "80" },
      { name: "height_mm", label: "Altura da lâmina (mm)", value: "12" },
    ],
    invert: true,
  },
  {
    key: "chaveiro_silhueta",
    title: "Chaveiro de silhueta",
    text: "O contorno do pet, pessoa ou desenho vira um chaveiro com furo para argola.",
    fields: [
      { name: "size_mm", label: "Tamanho (mm)", value: "50" },
      { name: "thickness_mm", label: "Espessura (mm)", value: "4" },
    ],
    invert: true,
  },
];

type Report = {
  prefix: string;
  combined: string;
  bbox_mm: number[];
  parts: { name: string; file: string }[];
  info: { faixas?: { parte: string; cor: string; de_mm: number; ate_mm: number }[]; trocar_filamento_em_mm?: number[]; dica?: string; aviso?: string };
  zip: string;
};

export function PhotoStudio() {
  const [mode, setMode] = useState<Mode>("litofania");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const current = MODES.find((m) => m.key === mode)!;

  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    const tick = async () => {
      const res = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
      const data = (await res.json()) as { status: string; result?: Report; error?: string };
      if (stop) return;
      setStatus(data.status);
      if (data.status === "concluido" && data.result) setReport(data.result);
      else if (data.status === "falhou" || !res.ok) setError(data.error ?? "Falha ao gerar.");
      else setTimeout(tick, 1500);
    };
    void tick();
    return () => {
      stop = true;
    };
  }, [jobId]);

  function submit(form: FormData) {
    setError(null);
    setReport(null);
    setStatus("enviando");
    start(async () => {
      const res = await startPhoto(form);
      if (res.error || !res.jobId) {
        setError(res.error ?? "Falha ao enviar.");
        setStatus(null);
      } else setJobId(res.jobId);
    });
  }

  const busy = pending || status === "enviando" || status === "fila" || status === "processando";
  const url = (file: string) => (report ? `/api/files/${report.prefix}/${file}` : "");

  return (
    <div className="grid gap-8 xl:grid-cols-2">
      <form action={submit} className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-2">
          {MODES.map((m) => (
            <label
              key={m.key}
              className={`cursor-pointer rounded-xl border p-3 text-sm ${mode === m.key ? "border-secondary bg-secondary/10" : "border-border"}`}
            >
              <input type="radio" name="mode" value={m.key} checked={mode === m.key} onChange={() => setMode(m.key)} className="sr-only" />
              <span className="font-medium">{m.title}</span>
              <span className="mt-1 block text-xs text-muted">{m.text}</span>
            </label>
          ))}
        </div>
        <Label label="Foto ou desenho (JPG, PNG, WEBP) *">
          <input type="file" name="file" accept=".jpg,.jpeg,.png,.webp" required className={inputClass} />
        </Label>
        <div key={mode} className="grid gap-4 sm:grid-cols-2">
          {current.fields.map((f) => (
            <Label key={f.name} label={f.label} hint={f.hint}>
              <input name={f.name} defaultValue={f.value} inputMode="decimal" className={inputClass} />
            </Label>
          ))}
          {current.invert && (
            <label className="flex items-center gap-2 self-end pb-2 text-sm">
              <input type="checkbox" name="invert" className="accent-[var(--secondary)]" />
              Inverter (forma clara sobre fundo escuro)
            </label>
          )}
        </div>
        <Button type="submit" disabled={busy}>
          {busy ? "Gerando…" : `Gerar ${current.title.toLowerCase()}`}
        </Button>
      </form>

      <div className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        {report && (
          <>
            <StlViewer key={report.prefix} url={url(report.combined)} color={mode === "litofania" ? "#F7F4EF" : "#14B8A6"} />
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Badge tone="ok">{report.bbox_mm.join(" × ")} mm</Badge>
              <a href={url(report.zip)} className="ml-auto rounded-xl bg-primary px-4 py-2 font-medium text-white">
                Baixar tudo (.zip)
              </a>
            </div>
            {report.info.faixas && (
              <div className="rounded-xl border border-border p-3 text-sm">
                <p className="mb-2 font-medium">Cores e alturas</p>
                <ul className="space-y-1">
                  {report.info.faixas.map((f) => (
                    <li key={f.parte} className="flex items-center gap-2">
                      <span className="size-4 rounded border border-border" style={{ background: f.cor }} />
                      {f.parte}: {f.de_mm}–{f.ate_mm} mm
                      <a href={url(`${f.parte}.stl`)} className="ml-auto text-secondary hover:underline">
                        STL
                      </a>
                    </li>
                  ))}
                </ul>
                {report.info.trocar_filamento_em_mm && (
                  <p className="mt-2 text-xs text-muted">Sem AMS: pause e troque o filamento em {report.info.trocar_filamento_em_mm.join(" mm, ")} mm.</p>
                )}
              </div>
            )}
            {report.info.dica && <p className="text-xs text-muted">{report.info.dica}</p>}
            {report.info.aviso && <Alert tone="error">{report.info.aviso}</Alert>}
          </>
        )}
      </div>
    </div>
  );
}
