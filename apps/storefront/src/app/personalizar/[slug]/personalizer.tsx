"use client";

import { useEffect, useState, useTransition } from "react";
import { StlViewer } from "@print3d/shared/stl-viewer";
import { requestPreview } from "@/actions/preview";
import type { Product } from "@/lib/store";
import { BuyBox } from "../../p/[slug]/buy-box";

/** Personalizador do chaveiro letra + nome (campos do modelo paramétrico, prévia 3D real). */
const STYLES = [
  ["letra_nome", "Letra + nome"],
  ["letra_cursiva_nome", "Letra cursiva + nome"],
  ["so_nome", "Só o nome"],
  ["inicial_data", "Inicial + data"],
] as const;
const FONTS = [
  ["", "Padrão do estilo"],
  ["cursiva", "Cursiva"],
  ["manuscrita", "Manuscrita"],
  ["retro", "Retrô"],
  ["bold", "Bold"],
  ["condensada", "Condensada"],
] as const;

type Preview = { status: string; prefix?: string; combined?: string; issues?: string[]; printable?: boolean };

export function Personalizer({ product }: { product: Product }) {
  const [style, setStyle] = useState("letra_nome");
  const [letter, setLetter] = useState("A");
  const [name, setName] = useState("");
  const [font, setFont] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    const tick = async () => {
      const res = await fetch(`/api/preview/${jobId}`, { cache: "no-store" });
      const data = (await res.json()) as Preview;
      if (stop) return;
      setPreview(data);
      if (data.status === "processando") setTimeout(tick, 1500);
    };
    void tick();
    return () => {
      stop = true;
    };
  }, [jobId]);

  function generate() {
    setError(null);
    setPreview({ status: "processando" });
    start(async () => {
      const res = await requestPreview(product.parametric_model!, {
        style,
        letter: style === "so_nome" ? null : letter,
        name,
        name_font: font || null,
      });
      if (res.error || !res.jobId) {
        setError(res.error ?? "Não foi possível gerar agora.");
        setPreview(null);
      } else setJobId(res.jobId);
    });
  }

  const ready = preview?.status === "concluido" && preview.printable;
  const personalization = { estilo: style, letra: style === "so_nome" ? "" : letter, nome: name, fonte: font };

  return (
    <div className="grid gap-10 lg:grid-cols-2">
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-2">
          {STYLES.map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setStyle(value)}
              className={`rounded-xl border px-3 py-3 text-sm ${style === value ? "border-ink bg-ink text-bg" : "border-border"}`}
            >
              {label}
            </button>
          ))}
        </div>
        {style !== "so_nome" && (
          <label className="block text-sm font-medium">
            Letra
            <input
              value={letter}
              maxLength={1}
              onChange={(e) => setLetter(e.target.value.toUpperCase())}
              className="mt-1 w-20 rounded-xl border border-border bg-surface px-3 py-3 text-center text-2xl font-bold"
            />
          </label>
        )}
        <label className="block text-sm font-medium">
          {style === "inicial_data" ? "Data (ex.: 12/10/2026)" : "Nome"}
          <input
            value={name}
            maxLength={14}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-xl border border-border bg-surface px-3 py-3"
          />
        </label>
        <label className="block text-sm font-medium">
          Fonte do nome
          <select value={font} onChange={(e) => setFont(e.target.value)} className="mt-1 w-full rounded-xl border border-border bg-surface px-3 py-3">
            {FONTS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={generate}
          disabled={pending || !name.trim() || preview?.status === "processando"}
          className="w-full rounded-xl border border-secondary bg-secondary/10 px-6 py-3 font-semibold text-secondary disabled:opacity-50"
        >
          {preview?.status === "processando" ? "Gerando seu chaveiro em 3D…" : "Ver em 3D"}
        </button>
        {error && <p className="rounded-xl bg-primary/10 p-3 text-sm text-primary">{error}</p>}
        {preview?.issues && preview.issues.length > 0 && (
          <ul className="rounded-xl bg-primary/10 p-3 text-sm text-primary">
            {preview.issues.map((i) => (
              <li key={i}>• {i}</li>
            ))}
          </ul>
        )}
        {ready && <BuyBox product={product} personalization={personalization} />}
      </div>
      <div>
        {preview?.status === "concluido" && preview.prefix ? (
          <StlViewer url={`/api/stl/${preview.prefix.split("/")[1]}/${preview.combined}`} color="#FF6B2C" />
        ) : (
          <div className="flex h-80 items-center justify-center rounded-xl border border-dashed border-border text-sm text-muted">
            Sua peça aparece aqui
          </div>
        )}
      </div>
    </div>
  );
}
