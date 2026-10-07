import { previewMl, publishMl, type MlListing, type MlPreview, type MlStatus } from "@/actions/mercadolivre";
import { MlTitle, ML_COLORS } from "@/components/ml-brand";
import { Badge, Button, Card, Label, inputClass } from "@/components/ui";
import { formatMoney } from "@/lib/form";
import type { Variant } from "@/lib/types";

type Query = { ml_variant?: string; ml_price?: string; ml_type?: string };

/** Anunciar uma variante no Mercado Livre: prévia com categoria e TARIFA REAL, depois publicar. */
export function MlPublish({
  productId,
  variants,
  status,
  listings,
  preview,
  previewError,
  query,
}: {
  productId: number;
  variants: Variant[];
  status: MlStatus;
  listings: MlListing[];
  preview: MlPreview | null;
  previewError: string | null;
  query: Query;
}) {
  if (!status.connected) {
    return (
      <Card title={<MlTitle>Mercado Livre</MlTitle>}>
        <p className="text-sm text-muted">Conecte a conta em Mercado Livre (precisa de domínio com HTTPS) para anunciar daqui.</p>
      </Card>
    );
  }
  const variantId = query.ml_variant ?? String(variants[0]?.id ?? "");
  return (
    <Card title={<MlTitle>Mercado Livre</MlTitle>}>
      <div id="ml" />
      {listings.map((l) => (
        <p key={l.id} className="mb-2 flex flex-wrap items-center gap-2 text-xs">
          <Badge tone={l.status === "publicado" ? "ok" : "danger"}>{l.status}</Badge>
          {formatMoney(l.price)} {l.permalink && <a className="text-secondary hover:underline" href={l.permalink} target="_blank" rel="noreferrer">abrir</a>}
          {l.last_error && <span className="text-primary">{l.last_error}</span>}
        </p>
      ))}
      <form action={previewMl.bind(null, productId)} className="space-y-3">
        <Label label="Variante">
          <select name="variant_id" defaultValue={variantId} className={inputClass}>
            {variants.map((v) => (
              <option key={v.id} value={v.id}>
                {v.size_label || v.sku}
              </option>
            ))}
          </select>
        </Label>
        <div className="grid grid-cols-2 gap-2">
          <Label label="Preço (R$)" hint="use o preço calculado para o ML">
            <input name="price" required inputMode="decimal" defaultValue={query.ml_price ?? ""} className={inputClass} />
          </Label>
          <Label label="Tipo">
            <select name="listing_type" defaultValue={query.ml_type ?? "gold_special"} className={inputClass}>
              <option value="gold_special">Clássico</option>
              <option value="gold_pro">Premium</option>
            </select>
          </Label>
        </div>
        <Button variant="secondary" className="w-full">
          Ver categoria e tarifa real
        </Button>
      </form>
      {previewError && <p className="mt-3 text-sm text-primary">{previewError}</p>}
      {preview && (
        <form action={publishMl.bind(null, productId)} className="mt-4 space-y-2 rounded-xl bg-bg p-3 text-sm">
          <input type="hidden" name="variant_id" value={variantId} />
          <input type="hidden" name="price" value={query.ml_price} />
          <input type="hidden" name="listing_type" value={query.ml_type} />
          <p>
            <b>{preview.title}</b>
          </p>
          <p className="text-xs text-muted">Categoria: {preview.category.name}</p>
          <p>
            Tarifa do ML: <b>{formatMoney(preview.fee)}</b>
            {preview.fee_percentage && ` (${preview.fee_percentage}%)`} · você recebe <b>{formatMoney(preview.net)}</b> antes do frete
          </p>
          {preview.required_attributes.map((a) => (
            <Label key={a.id} label={`${a.name} (obrigatório)`}>
              <input name={`attr_${a.id}`} className={inputClass} placeholder={a.id === "BRAND" ? "vazio = nome da loja" : ""} />
            </Label>
          ))}
          <button
            className="w-full rounded-xl px-4 py-2.5 text-sm font-bold shadow-sm transition hover:brightness-95"
            style={{ background: ML_COLORS.yellow, color: ML_COLORS.navy }}
          >
            Publicar no Mercado Livre
          </button>
        </form>
      )}
    </Card>
  );
}
