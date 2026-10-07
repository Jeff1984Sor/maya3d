import { imageAction, releaseImage, runVisualCheck, type ProductImage } from "@/actions/content";
import { PhotoUploader } from "@/components/photo-uploader";
import { Badge, Button, Card, inputClass } from "@/components/ui";

const VISUAL: Record<ProductImage["visual_status"], { label: string; tone: "ok" | "warn" | "danger" | "muted" }> = {
  pendente: { label: "não verificada", tone: "muted" },
  ok: { label: "👁️ ok", tone: "ok" },
  alerta: { label: "👁️ atenção", tone: "warn" },
  bloqueado: { label: "👁️ bloqueada", tone: "danger" },
  liberado: { label: "liberada por você", tone: "ok" },
  erro: { label: "não analisada", tone: "muted" },
};

/** Fotos do produto: a primeira é a capa na loja. O Guardião visual confere cada uma. */
export function ProductImages({ productId, images }: { productId: number; images: ProductImage[] }) {
  return (
    <Card title="📷 Fotos">
      {images.length === 0 && <p className="mb-3 text-sm text-muted">Sem fotos: a loja mostra um ícone no lugar. Envie ao menos uma.</p>}
      {images.length > 0 && (
        <div className="mb-4 space-y-3">
          {images.map((img, i) => {
            const v = VISUAL[img.visual_status] ?? VISUAL.pendente;
            const findings = img.visual_notes?.findings ?? [];
            return (
              <div key={img.id} className="flex gap-3 rounded-xl border border-border p-2">
                {/* eslint-disable-next-line @next/next/no-img-element -- miniatura pelo proxy do painel */}
                <img src={`/api/files/${img.thumb_key}`} alt="" className="size-20 shrink-0 rounded-lg bg-white object-cover" />
                <div className="min-w-0 flex-1 space-y-1 text-xs">
                  <div className="flex flex-wrap items-center gap-1">
                    {i === 0 && <Badge tone="ok">capa</Badge>}
                    <Badge tone={v.tone}>{v.label}</Badge>
                  </div>
                  {img.visual_notes?.summary && <p className="text-muted">{img.visual_notes.summary}</p>}
                  {findings.length > 0 && (
                    <ul className="text-primary">
                      {findings.map((f, j) => (
                        <li key={j}>
                          {f.kind}: {f.description} ({Math.round(f.confidence * 100)}%)
                        </li>
                      ))}
                    </ul>
                  )}
                  {img.visual_notes?.released_reason && <p className="text-muted">Motivo: {img.visual_notes.released_reason}</p>}
                  {(img.visual_status === "bloqueado" || img.visual_status === "alerta") && (
                    <form action={releaseImage.bind(null, productId, img.id)} className="flex gap-1">
                      <input name="reason" required minLength={5} placeholder="por que pode? ex.: desenho próprio" className={`${inputClass} py-1 text-xs`} />
                      <Button variant="secondary" className="px-2 py-1 text-xs">
                        Liberar
                      </Button>
                    </form>
                  )}
                  <div className="flex gap-3">
                    {i > 0 && (
                      <form action={imageAction.bind(null, productId, img.id, "cover")}>
                        <button className="text-secondary hover:underline">tornar capa</button>
                      </form>
                    )}
                    <form action={imageAction.bind(null, productId, img.id, "delete")}>
                      <button className="text-primary hover:underline">remover</button>
                    </form>
                  </div>
                </div>
              </div>
            );
          })}
          <form action={runVisualCheck.bind(null, productId)}>
            <Button variant="secondary" className="w-full">
              👁️ Verificar fotos com IA
            </Button>
          </form>
        </div>
      )}
      <PhotoUploader productId={productId} />
    </Card>
  );
}
