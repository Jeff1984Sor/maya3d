"use client";

import { useEffect, useState, useTransition } from "react";
import { startSplit } from "@/actions/split";
import { StlViewer } from "@/components/stl-viewer";
import { Alert, Badge, Button, Label, inputClass } from "@/components/ui";

type Printer = { id: number; name: string; bed_x_mm: number; bed_y_mm: number; bed_z_mm: number };
type Report = {
  prefix: string;
  plan: { counts: number[]; cell_mm: number[] };
  pieces: { name: string; file: string; bbox_mm: number[]; volume_cm3: number; fits: boolean }[];
  pins: { count: number; file: string | null };
  faces_without_pins: number;
  exploded: string;
  zip: string;
};

const POLL_MS = 2000;

export function SplitStudio({ printers }: { printers: Printer[] }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    const tick = async () => {
      const res = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
      const data = (await res.json()) as { status: string; result?: Report; error?: string };
      if (stop) return;
      setStatus(data.status);
      if (data.status === "concluido" && data.result) {
        setReport(data.result);
        setPreview(data.result.exploded);
      } else if (data.status === "falhou" || !res.ok) {
        setError(data.error ?? "Falha na divisão.");
      } else {
        setTimeout(tick, POLL_MS);
      }
    };
    void tick();
    return () => {
      stop = true;
    };
  }, [jobId]);

  function submit(form: FormData) {
    setError(null);
    setReport(null);
    setJobId(null);
    setStatus("enviando");
    start(async () => {
      const res = await startSplit(form);
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
      <form action={submit} className="grid content-start gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Label label="Arquivo da peça (STL, OBJ, PLY) *">
            <input type="file" name="file" accept=".stl,.obj,.ply" required className={inputClass} />
          </Label>
        </div>
        <Label label="Impressora *" hint="o tamanho da mesa define os cortes">
          <select name="printer_id" className={inputClass}>
            {printers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.bed_x_mm}×{p.bed_y_mm}×{p.bed_z_mm} mm)
              </option>
            ))}
          </select>
        </Label>
        <Label label="Diâmetro do pino (mm)" hint="pode usar filamento 1,75 mm ou palito no lugar">
          <input name="pin_diameter_mm" defaultValue="4" inputMode="decimal" className={inputClass} />
        </Label>
        <Label label="Folga do furo (mm)" hint="0,2–0,3 para PLA">
          <input name="clearance_mm" defaultValue="0.25" inputMode="decimal" className={inputClass} />
        </Label>
        <Label label="Folga de borda da mesa (mm)">
          <input name="margin_mm" defaultValue="3" inputMode="decimal" className={inputClass} />
        </Label>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={busy}>
            {busy ? (status === "processando" ? "Cortando e furando…" : "Enviando…") : "Dividir peça"}
          </Button>
        </div>
      </form>

      <div className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        {report && (
          <>
            {preview && <StlViewer key={preview} url={url(preview)} />}
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Badge tone="ok">{report.pieces.length} pedaço(s)</Badge>
              <Badge>cortes {report.plan.counts.join(" × ")}</Badge>
              <Badge>{report.pins.count} pino(s)</Badge>
              <a href={url(report.zip)} className="ml-auto rounded-xl bg-primary px-4 py-2 font-medium text-white">
                Baixar tudo (.zip)
              </a>
            </div>
            {report.faces_without_pins > 0 && (
              <Alert tone="error">
                {report.faces_without_pins} face(s) de corte finas demais para pino: nelas, só cola.
              </Alert>
            )}
            <ul className="divide-y divide-border rounded-xl border border-border text-sm">
              <li className="flex items-center gap-2 px-3 py-2">
                <button type="button" className="text-secondary hover:underline" onClick={() => setPreview(report.exploded)}>
                  vista explodida (montagem)
                </button>
              </li>
              {report.pieces.map((p) => (
                <li key={p.name} className="flex flex-wrap items-center gap-2 px-3 py-2">
                  <button type="button" className="font-medium hover:text-secondary" onClick={() => setPreview(p.file)}>
                    {p.name.replace("peca_", "Pedaço ")}
                  </button>
                  <span className="text-muted">
                    {p.bbox_mm.join(" × ")} mm · {p.volume_cm3} cm³
                  </span>
                  {p.fits ? <Badge tone="ok">cabe</Badge> : <Badge tone="danger">não cabe</Badge>}
                  <a href={url(p.file)} className="ml-auto text-secondary hover:underline">
                    STL
                  </a>
                </li>
              ))}
              {report.pins.file && (
                <li className="flex items-center gap-2 px-3 py-2">
                  <button type="button" className="font-medium hover:text-secondary" onClick={() => setPreview(report.pins.file)}>
                    Pinos de encaixe ({report.pins.count})
                  </button>
                  <a href={url(report.pins.file)} className="ml-auto text-secondary hover:underline">
                    STL
                  </a>
                </li>
              )}
            </ul>
            <p className="text-xs text-muted">
              Montagem: encaixe os pinos com cola nos furos de um pedaço, passe cola na face de corte e feche com o vizinho. O nome do arquivo
              indica a posição (Pedaço 1_2_1 = 1º no comprimento, 2º na largura, 1º na altura).
            </p>
          </>
        )}
      </div>
    </div>
  );
}
