import type { MlListing } from "@/actions/mercadolivre";
import { publishShopee, type ShopeeStatus } from "@/actions/shopee";
import { SHOPEE_COLOR, ShopeeTitle } from "@/components/shopee-brand";
import { Badge, Card, Label, inputClass } from "@/components/ui";
import { formatMoney } from "@/lib/form";
import type { Variant } from "@/lib/types";

/** Anunciar uma variante na Shopee: categoria sugerida, fotos enviadas e canais de envio ativos. */
export function ShopeePublish({
  productId,
  variants,
  status,
  listings,
}: {
  productId: number;
  variants: Variant[];
  status: ShopeeStatus;
  listings: MlListing[];
}) {
  return (
    <Card title={<ShopeeTitle>Shopee</ShopeeTitle>}>
      {!status.connected ? (
        <p className="text-sm text-muted">Conecte a loja em Shopee (precisa de domínio com HTTPS) para anunciar daqui.</p>
      ) : (
        <>
          {listings.map((l) => (
            <p key={l.id} className="mb-2 flex flex-wrap items-center gap-2 text-xs">
              <Badge tone={l.status === "publicado" ? "ok" : "danger"}>{l.status}</Badge>
              {formatMoney(l.price)}
              {l.last_error && <span className="text-primary">{l.last_error}</span>}
            </p>
          ))}
          <form action={publishShopee.bind(null, productId)} className="space-y-3">
            <Label label="Variante">
              <select name="variant_id" className={inputClass}>
                {variants.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.size_label || v.sku}
                  </option>
                ))}
              </select>
            </Label>
            <Label label="Preço (R$)" hint="use o preço calculado para a Shopee">
              <input name="price" required inputMode="decimal" className={inputClass} />
            </Label>
            <button
              className="w-full rounded-xl px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:brightness-95"
              style={{ background: SHOPEE_COLOR }}
            >
              Publicar na Shopee
            </button>
          </form>
        </>
      )}
    </Card>
  );
}
