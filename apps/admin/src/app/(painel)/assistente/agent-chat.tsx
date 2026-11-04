"use client";

import { type FormEvent, useEffect, useRef, useState, useTransition } from "react";
import Link from "next/link";
import { askAgent, confirmProposal, type AgentTurn, type ImageCard, type Proposal } from "@/actions/agent";
import { Alert, Badge, Button, inputClass } from "@/components/ui";

type Entry = {
  role: "user" | "assistant";
  text: string;
  memo?: string;
  images?: ImageCard[];
  proposals?: Proposal[];
};

const EXAMPLES = ["Busca fotos de um cachorro sentado", "Quais produtos estão em rascunho?", "Como estão os pedidos?"];

type JobFile = { label: string; href: string };
type JobState = { status: string; progress?: number; files?: JobFile[]; error?: string };
type JobResult = { prefix: string; combined?: string; zip?: string; model?: string; project?: string };

/** Acompanha a peça gerada depois da confirmação (fila do worker ou IA de 3D). */
function JobProgress({ job }: { job: string }) {
  const [state, setState] = useState<JobState>({ status: "fila" });
  useEffect(() => {
    let stop = false;
    const [kind, id] = job.split(":");
    const tick = async () => {
      const res = await fetch(kind === "ia" ? `/api/photo3d/${id}` : `/api/jobs/${id}`, { cache: "no-store" });
      const data = (await res.json()) as { status: string; progress?: number; error?: string; result?: JobResult };
      if (stop) return;
      if (data.status === "concluido" && data.result) {
        const r = data.result;
        const href = (f: string) => `/api/files/${r.prefix}/${f}`;
        const stl = r.model ?? r.combined;
        const files: JobFile[] = [];
        if (r.project) files.push({ label: "Abrir no Bambu Studio (.3mf)", href: href(r.project) });
        if (stl) files.push({ label: "STL", href: href(stl) });
        if (r.zip) files.push({ label: "Tudo (.zip)", href: href(r.zip) });
        setState({ status: "concluido", files });
      } else if (data.status === "falhou" || !res.ok) {
        setState({ status: "falhou", error: data.error ?? "falhou" });
      } else {
        setState({ status: data.status, progress: data.progress });
        setTimeout(tick, kind === "ia" ? 5000 : 2000);
      }
    };
    void tick();
    return () => {
      stop = true;
    };
  }, [job]);

  if (state.status === "falhou") return <Alert tone="error">{state.error}</Alert>;
  if (state.status !== "concluido") return <p className="text-xs text-muted">Gerando… {state.progress ? `${state.progress}%` : ""}</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {state.files?.map((f) => (
        <a key={f.href} href={f.href} className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-white">
          {f.label}
        </a>
      ))}
    </div>
  );
}

function ProposalCard({ proposal }: { proposal: Proposal }) {
  const [state, setState] = useState<"aberta" | "enviando" | "feita" | "cancelada">("aberta");
  const [message, setMessage] = useState<string | null>(null);
  const [job, setJob] = useState<string | null>(null);
  const [productId, setProductId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setState("enviando");
    setError(null);
    const res = await confirmProposal(proposal.id);
    if ("error" in res) {
      setError(res.error);
      setState("aberta");
      return;
    }
    setMessage(res.message);
    setJob(res.job);
    setProductId(res.product_id);
    setState("feita");
  }

  return (
    <div className="space-y-2 rounded-xl border border-secondary bg-secondary/5 p-3 text-sm">
      <p>{proposal.summary}</p>
      {error && <Alert tone="error">{error}</Alert>}
      {state === "aberta" || state === "enviando" ? (
        <div className="flex items-center gap-3">
          <Button type="button" onClick={confirm} disabled={state === "enviando"}>
            {state === "enviando" ? "Fazendo…" : "Confirmar"}
          </Button>
          <button type="button" className="text-xs text-muted hover:underline" onClick={() => setState("cancelada")}>
            cancelar
          </button>
        </div>
      ) : state === "cancelada" ? (
        <Badge>cancelada</Badge>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="ok">{message}</Badge>
            {productId && (
              <Link href={`/produtos/${productId}`} className="text-xs text-secondary hover:underline">
                abrir produto →
              </Link>
            )}
          </div>
          {job && <JobProgress job={job} />}
        </>
      )}
    </div>
  );
}

function ImageGrid({ images, onPick }: { images: ImageCard[]; onPick: (n: number) => void }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {images.map((img) => (
        <figure key={img.id} className="overflow-hidden rounded-xl border border-border">
          <button type="button" onClick={() => onPick(img.number)} className="block w-full" title="usar esta imagem">
            {/* eslint-disable-next-line @next/next/no-img-element -- miniatura externa do acervo de licença aberta */}
            <img src={img.thumbnail} alt={img.title} className="aspect-square w-full bg-bg object-cover" loading="lazy" />
          </button>
          <figcaption className="space-y-0.5 p-2 text-xs">
            <p className="font-medium">
              #{img.number} {img.title}
            </p>
            <p className="text-muted">
              {img.license} · {img.creator}
              {img.source_page && (
                <>
                  {" · "}
                  <a href={img.source_page} target="_blank" rel="noreferrer" className="text-secondary hover:underline">
                    origem
                  </a>
                </>
              )}
            </p>
          </figcaption>
        </figure>
      ))}
    </div>
  );
}

export function AgentChat() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const input = useRef<HTMLTextAreaElement>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries, pending]);

  function send(text: string) {
    const clean = text.trim();
    if (!clean || pending) return;
    const next: Entry[] = [...entries, { role: "user", text: clean }];
    setEntries(next);
    setError(null);
    if (input.current) input.current.value = "";
    const turns: AgentTurn[] = next.map((e) => ({ role: e.role, content: (e.memo ?? e.text).slice(0, 4000) }));
    start(async () => {
      const res = await askAgent(turns);
      if ("error" in res) {
        setError(res.error);
        return;
      }
      setEntries([...next, { role: "assistant", text: res.reply, memo: res.memo, images: res.images, proposals: res.proposals }]);
    });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    send(input.current?.value ?? "");
  }

  return (
    <div className="space-y-4">
      <div className="max-h-[65vh] space-y-4 overflow-y-auto">
        {entries.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((e) => (
              <button key={e} type="button" onClick={() => send(e)} className="rounded-full border border-border px-3 py-1.5 text-sm hover:border-secondary">
                {e}
              </button>
            ))}
          </div>
        )}
        {entries.map((e, i) => (
          <div key={i} className={e.role === "user" ? "flex justify-end" : "space-y-3"}>
            <p className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${e.role === "user" ? "bg-primary text-white" : "bg-bg"}`}>{e.text}</p>
            {e.images && e.images.length > 0 && (
              <ImageGrid images={e.images} onPick={(n) => send(`Quero usar a imagem ${n}. Que peça você sugere?`)} />
            )}
            {e.proposals?.map((p) => <ProposalCard key={p.id} proposal={p} />)}
          </div>
        ))}
        {pending && <p className="text-sm text-muted">Pensando…</p>}
        <div ref={bottom} />
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      <form onSubmit={submit} className="flex gap-2">
        <textarea
          ref={input}
          rows={2}
          placeholder="Ex.: busca fotos de um cachorro sentado / faz uma litofania da 2 com 120 mm"
          className={inputClass}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(e.currentTarget.value);
            }
          }}
        />
        <Button type="submit" disabled={pending}>
          Enviar
        </Button>
      </form>
      <p className="text-xs text-muted">
        As fotos vêm do Openverse e só aparecem as que têm licença aberta que permite uso comercial. Algumas licenças pedem crédito ao autor (veja a
        origem). Não use foto de marca, personagem ou de pessoas sem autorização.
      </p>
    </div>
  );
}
