"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type Item = { name: string; size: number; progress: number; error?: string; done?: boolean };

const ACCEPT = ".zip,.stl,.3mf,.obj,.png,.jpg,.jpeg,.webp";
const mb = (b: number) => `${(b / 1024 / 1024).toFixed(b > 10 * 1024 * 1024 ? 0 : 1)} MB`;

function upload(slug: string, file: File, onProgress: (p: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/library/${slug}/upload`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      if (xhr.status < 300) return resolve();
      let detail = `erro ${xhr.status}`;
      try {
        detail = JSON.parse(xhr.responseText).detail ?? detail;
      } catch {}
      reject(new Error(typeof detail === "string" ? detail : `erro ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error("conexão caiu"));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

/** Envia vários arquivos, um por vez, com progresso. Arraste e solte ou escolha. */
export function LibraryUploader({ slug }: { slug: string }) {
  const router = useRouter();
  const [items, setItems] = useState<Item[]>([]);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);

  async function send(files: File[]) {
    if (!files.length || busy) return;
    setBusy(true);
    const start = items.length;
    setItems((cur) => [...cur, ...files.map((f) => ({ name: f.name, size: f.size, progress: 0 }))]);
    for (const [i, file] of files.entries()) {
      const idx = start + i;
      const patch = (p: Partial<Item>) => setItems((cur) => cur.map((it, j) => (j === idx ? { ...it, ...p } : it)));
      try {
        await upload(slug, file, (progress) => patch({ progress }));
        patch({ progress: 1, done: true });
      } catch (e) {
        patch({ error: e instanceof Error ? e.message : "falhou" });
      }
    }
    setBusy(false);
    router.refresh();
  }

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (busy) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [busy]);

  return (
    <div>
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          void send(Array.from(e.dataTransfer.files));
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed p-8 text-center text-sm ${
          over ? "border-secondary bg-secondary/5" : "border-border"
        }`}
      >
        <span className="font-medium">Arraste os arquivos aqui ou clique para escolher</span>
        <span className="text-xs text-muted">ZIP, STL, 3MF, OBJ e imagens (capa). Pode mandar a pasta inteira zipada.</span>
        <input
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          disabled={busy}
          onChange={(e) => void send(Array.from(e.target.files ?? []))}
        />
      </label>
      {items.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs">
          {items.map((it, i) => (
            <li key={i} className="flex items-center gap-2">
              <span className="w-56 truncate">{it.name}</span>
              <span className="w-16 text-muted">{mb(it.size)}</span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg">
                <span
                  className={`block h-full ${it.error ? "bg-primary" : "bg-secondary"}`}
                  style={{ width: `${Math.round(it.progress * 100)}%` }}
                />
              </span>
              <span className={it.error ? "text-primary" : "text-muted"}>{it.error ?? (it.done ? "ok" : `${Math.round(it.progress * 100)}%`)}</span>
            </li>
          ))}
        </ul>
      )}
      {busy && <p className="mt-2 text-xs text-muted">Enviando… não feche esta aba.</p>}
    </div>
  );
}

/** Enquanto processa, recarrega a tela a cada 5 s. */
export function AutoRefresh({ active }: { active: boolean }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => router.refresh(), 5000);
    return () => clearInterval(t);
  }, [active, router]);
  return null;
}
