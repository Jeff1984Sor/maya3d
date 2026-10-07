"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

type Item = { file: File; preview: string; progress: number; error?: string; done?: boolean };

const ACCEPT = "image/jpeg,image/png,image/webp";
const MAX_MB = 20;

function send(productId: number, file: File, onProgress: (p: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/products/${productId}/images`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      if (xhr.status < 300) return resolve();
      let detail = `erro ${xhr.status}`;
      try {
        const body = JSON.parse(xhr.responseText) as { detail?: unknown };
        if (typeof body.detail === "string") detail = body.detail;
      } catch {}
      reject(new Error(detail));
    };
    xhr.onerror = () => reject(new Error("conexão caiu"));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

/** 1) Escolher fotos (com prévia)  2) Enviar (com progresso e erro no próprio card). */
export function PhotoUploader({ productId }: { productId: number }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => () => items.forEach((i) => URL.revokeObjectURL(i.preview)), [items]);

  function pick(files: FileList | null) {
    if (!files) return;
    const next: Item[] = [];
    for (const file of Array.from(files)) {
      if (!ACCEPT.split(",").includes(file.type)) {
        setMessage(`${file.name}: use JPG, PNG ou WebP`);
        continue;
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        setMessage(`${file.name}: acima de ${MAX_MB} MB`);
        continue;
      }
      next.push({ file, preview: URL.createObjectURL(file), progress: 0 });
    }
    setItems((cur) => [...cur.filter((i) => !i.done), ...next]);
    if (input.current) input.current.value = "";
  }

  async function upload() {
    setBusy(true);
    setMessage(null);
    let ok = 0;
    for (const [idx, item] of items.entries()) {
      if (item.done) continue;
      const patch = (p: Partial<Item>) => setItems((cur) => cur.map((it, j) => (j === idx ? { ...it, ...p } : it)));
      try {
        await send(productId, item.file, (progress) => patch({ progress }));
        patch({ progress: 1, done: true, error: undefined });
        ok++;
      } catch (e) {
        patch({ error: e instanceof Error ? e.message : "falhou" });
      }
    }
    setBusy(false);
    setMessage(ok ? `${ok} foto(s) enviada(s) ✓` : null);
    router.refresh();
    setItems((cur) => cur.filter((i) => !i.done));
  }

  const pending = items.filter((i) => !i.done).length;
  return (
    <div className="space-y-3">
      <input ref={input} type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => pick(e.target.files)} />
      <button
        type="button"
        onClick={() => input.current?.click()}
        disabled={busy}
        className="w-full rounded-xl border-2 border-dashed border-border px-4 py-4 text-sm font-medium hover:border-secondary disabled:opacity-50"
      >
        📁 Escolher fotos
      </button>
      {items.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {items.map((it, i) => (
            <div key={it.preview} className="relative overflow-hidden rounded-lg border border-border bg-white">
              {/* eslint-disable-next-line @next/next/no-img-element -- prévia local antes de enviar */}
              <img src={it.preview} alt="" className="aspect-square w-full object-cover" />
              {!busy && (
                <button
                  type="button"
                  aria-label="Tirar esta foto"
                  onClick={() => setItems((cur) => cur.filter((_, j) => j !== i))}
                  className="absolute right-1 top-1 rounded-full bg-black/60 px-1.5 text-xs text-white"
                >
                  ✕
                </button>
              )}
              <span className="absolute inset-x-0 bottom-0 h-1 bg-black/10">
                <span className={`block h-full ${it.error ? "bg-primary" : "bg-secondary"}`} style={{ width: `${Math.round(it.progress * 100)}%` }} />
              </span>
              {it.error && <p className="absolute inset-x-0 bottom-1 bg-primary/90 px-1 text-[10px] text-white">{it.error}</p>}
            </div>
          ))}
        </div>
      )}
      <button
        type="button"
        onClick={() => void upload()}
        disabled={busy || pending === 0}
        className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-40"
      >
        {busy ? "Enviando…" : pending ? `⬆️ Enviar ${pending} foto(s)` : "⬆️ Enviar"}
      </button>
      {message && <p className="text-xs text-secondary">{message}</p>}
      <p className="text-xs text-muted">JPG, PNG ou WebP até {MAX_MB} MB. O sistema otimiza, tira a localização e o Guardião visual confere.</p>
    </div>
  );
}
