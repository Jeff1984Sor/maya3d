import Link from "next/link";
import { notFound } from "next/navigation";
import { addVariant, deleteProduct, deleteVariant, setStatus, updateProduct } from "@/actions/products";
import type { ChannelCopy } from "@/actions/ai";
import type { ProductImage } from "@/actions/content";
import type { MlListing, MlPreview, MlStatus } from "@/actions/mercadolivre";
import type { ShopeeStatus } from "@/actions/shopee";
import { ChannelCopyPanel } from "@/components/channel-copy-panel";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { Flash } from "@/components/flash";
import { GuardianBadge, StatusBadge } from "@/components/product-badges";
import { MlPublish } from "@/components/ml-publish";
import { ProductForm } from "@/components/product-form";
import { ProductImages } from "@/components/product-images";
import { ShopeePublish } from "@/components/shopee-publish";
import { Alert, Badge, Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { AdminApiError, api } from "@/lib/admin-api";
import { formatMoney } from "@/lib/form";
import type { Material, Niche, ProductDetail, Variant, VariantQuote } from "@/lib/types";

type Packaging = { id: number; name: string; cost: string };

export default async function ProdutoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ ok?: string; erro?: string; ml_variant?: string; ml_price?: string; ml_type?: string }>;
}) {
  const id = Number((await params).id);
  const query = await searchParams;
  if (!Number.isInteger(id)) notFound();

  let product: ProductDetail;
  try {
    product = await api.get<ProductDetail>(`/products/${id}`);
  } catch (error) {
    if (error instanceof AdminApiError && error.status === 404) notFound();
    throw error;
  }
  const [niches, materials, packaging, copies, images, mlStatus, mlListings, spStatus, spListings, quotes] = await Promise.all([
    api.get<Niche[]>("/niches"),
    api.get<Material[]>("/materials"),
    api.get<Packaging[]>("/packaging"),
    api.get<ChannelCopy[]>(`/ai/channel-copy?product_id=${id}`),
    api.get<ProductImage[]>(`/products/${id}/images`),
    api.get<MlStatus>("/mercadolivre/status"),
    api.get<MlListing[]>(`/mercadolivre/listings?product_id=${id}`),
    api.get<ShopeeStatus>("/shopee/status"),
    api.get<MlListing[]>(`/shopee/listings?product_id=${id}`),
    Promise.all(product.variants.map((v) => api.get<VariantQuote>(`/products/${id}/variants/${v.id}/quote`))),
  ]);
  let mlPreview: MlPreview | null = null;
  let mlPreviewError: string | null = null;
  if (query.ml_variant && query.ml_price && mlStatus.connected) {
    try {
      mlPreview = await api.post<MlPreview>("/mercadolivre/preview", {
        variant_id: Number(query.ml_variant),
        price: query.ml_price,
        listing_type: query.ml_type ?? "gold_special",
      });
    } catch (error) {
      mlPreviewError = error instanceof AdminApiError ? error.message : "Falha ao consultar o Mercado Livre.";
    }
  }
  const materialName = (mid: string) => {
    const m = materials.find((x) => String(x.id) === mid);
    return m ? `${m.kind} ${m.color_name}` : `material ${mid}`;
  };

  return (
    <>
      <PageHeader title={product.title} description={`${product.niche} · ${product.category}`}>
        <Link href="/produtos" className="text-sm text-secondary hover:underline">
          ← produtos
        </Link>
      </PageHeader>
      <Flash ok={query.ok} erro={query.erro} />

      <div className="mb-6 flex flex-wrap items-center gap-2">
        <StatusBadge product={product} />
        <GuardianBadge status={product.guardian_status} />
        {product.age_rating && <Badge>{product.age_rating}</Badge>}
        <div className="ml-auto flex gap-2">
          {product.status !== "ativo" && (
            <form action={setStatus.bind(null, id, "ativo")}>
              <Button type="submit">Ativar</Button>
            </form>
          )}
          {product.status === "ativo" && (
            <form action={setStatus.bind(null, id, "pausado")}>
              <Button type="submit" variant="secondary">
                Pausar
              </Button>
            </form>
          )}
          <form action={deleteProduct.bind(null, id)}>
            <ConfirmSubmit message="Remover o produto e todas as variantes?" className="rounded-xl px-4 py-2 text-sm text-primary hover:bg-primary/10">
              Remover
            </ConfirmSubmit>
          </form>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          <Card title="Variantes e preço por canal">
            {product.variants.length === 0 && <p className="mb-4 text-sm text-muted">Nenhuma variante ainda.</p>}
            <div className="space-y-4">
              {product.variants.map((v, i) => (
                <VariantCard key={v.id} productId={id} variant={v} quote={quotes[i]!} materialName={materialName} />
              ))}
            </div>
            <details className="mt-6 rounded-xl border border-border p-4">
              <summary className="cursor-pointer text-sm font-medium">Adicionar variante</summary>
              <form action={addVariant.bind(null, id)} className="mt-4 grid gap-4 sm:grid-cols-2">
                <Label label="Tamanho/rótulo" hint="ex.: 15cm, P, kit 10">
                  <input name="size_label" className={inputClass} />
                </Label>
                <Label label="Acabamento">
                  <select name="finish" className={inputClass}>
                    <option value="cor_unica">Cor única</option>
                    <option value="pintada">Pintada à mão</option>
                  </select>
                </Label>
                {[1, 2].map((n) => (
                  <div key={n} className="grid grid-cols-[1fr_6rem] gap-2 sm:col-span-2">
                    <Label label={`Material (cor ${n})`}>
                      <select name={`material_${n}`} className={inputClass} defaultValue="">
                        <option value="">—</option>
                        {materials.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.kind} {m.color_name}
                          </option>
                        ))}
                      </select>
                    </Label>
                    <Label label="Gramas">
                      <input name={`grams_${n}`} inputMode="decimal" className={inputClass} />
                    </Label>
                  </div>
                ))}
                <Label label="Tempo de impressão (h)" hint="do fatiador; vazio = a confirmar">
                  <input name="print_hours" inputMode="decimal" className={inputClass} />
                </Label>
                <Label label="Pós-processamento (min)">
                  <input name="post_minutes" type="number" min={0} defaultValue={0} className={inputClass} />
                </Label>
                <Label label="Embalagem">
                  <select name="packaging_id" className={inputClass} defaultValue="">
                    <option value="">—</option>
                    {packaging.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({formatMoney(p.cost)})
                      </option>
                    ))}
                  </select>
                </Label>
                <Label label="Peso embalado (g)">
                  <input name="packed_weight_g" type="number" min={1} className={inputClass} />
                </Label>
                <Label label="SKU" hint="vazio = automático">
                  <input name="sku" className={inputClass} />
                </Label>
                <div className="sm:col-span-2">
                  <Button type="submit">Adicionar variante</Button>
                </div>
              </form>
            </details>
          </Card>

          <ChannelCopyPanel productId={id} copies={copies} />

          <Card title="Dados do produto">
            <ProductForm niches={niches} product={product} action={updateProduct.bind(null, id)} submitLabel="Salvar e verificar" />
          </Card>
        </div>

        <aside className="space-y-6">
          <ProductImages productId={id} images={images} />
          <MlPublish
            productId={id}
            variants={product.variants}
            status={mlStatus}
            listings={mlListings}
            preview={mlPreview}
            previewError={mlPreviewError}
            query={query}
          />
          <ShopeePublish productId={id} variants={product.variants} status={spStatus} listings={spListings} />
          <Card title="Guardião">
            {product.guardian_status === "bloqueado" ? (
              <Alert tone="error">{product.guardian_reason}</Alert>
            ) : (
              <p className="mb-3 text-sm text-muted">Nenhum problema encontrado nas regras.</p>
            )}
            {(product.disclaimers.length > 0 || product.attribution_required) && (
              <>
                <p className="mb-2 text-sm font-medium">O anúncio precisa ter</p>
                <ul className="list-inside list-disc space-y-1 text-sm text-muted">
                  {product.attribution_required && <li>Atribuição: {product.design.author ?? "autor"} (CC BY)</li>}
                  {product.disclaimers.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              </>
            )}
          </Card>
          <Card title="Origem">
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Design</dt>
                <dd>{product.design.name}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Origem</dt>
                <dd>{product.design.origin}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Licença</dt>
                <dd>{product.design.license}</dd>
              </div>
            </dl>
          </Card>
        </aside>
      </div>
    </>
  );
}

function VariantCard({
  productId,
  variant,
  quote,
  materialName,
}: {
  productId: number;
  variant: Variant;
  quote: VariantQuote;
  materialName: (id: string) => string;
}) {
  return (
    <div className="rounded-xl border border-border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm">{variant.sku}</span>
        {variant.size_label && <Badge>{variant.size_label}</Badge>}
        <Badge>{variant.finish === "pintada" ? "pintada à mão" : "cor única"}</Badge>
        <Badge tone={variant.slicing_source === "a_confirmar" ? "warn" : "ok"}>
          {variant.slicing_source === "a_confirmar" ? "gramas/tempo a confirmar" : `dados: ${variant.slicing_source}`}
        </Badge>
        <form action={deleteVariant.bind(null, productId, variant.id)} className="ml-auto">
          <ConfirmSubmit message="Remover esta variante?" className="text-xs text-primary hover:underline">
            remover
          </ConfirmSubmit>
        </form>
      </div>
      {variant.grams_by_material && Object.keys(variant.grams_by_material).length === 1 && variant.print_seconds && (
        <Link
          className="mt-2 inline-block text-xs text-secondary hover:underline"
          href={`/comparativo?${new URLSearchParams({
            ref: Object.keys(variant.grams_by_material)[0]!,
            grams: String(Object.values(variant.grams_by_material)[0]),
            hours: (variant.print_seconds / 3600).toFixed(2),
            post: String(variant.post_minutes),
          })}`}
        >
          comparar em outros materiais →
        </Link>
      )}
      {variant.grams_by_material && (
        <p className="mt-2 text-xs text-muted">
          {Object.entries(variant.grams_by_material)
            .map(([m, g]) => `${materialName(m)}: ${g} g`)
            .join(" · ")}
          {variant.print_seconds ? ` · ${(variant.print_seconds / 3600).toFixed(1)} h` : ""}
        </p>
      )}
      {quote.ready ? (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <tbody>
              <tr className="text-muted">
                <td className="py-1">Custo</td>
                <td className="py-1 text-right">{formatMoney(quote.cost_total)}</td>
                <td />
              </tr>
              {quote.quotes.map((q) => (
                <tr key={q.channel} className="border-t border-border">
                  <td className="py-1">{q.channel}</td>
                  {q.error ? (
                    <td colSpan={2} className="py-1 text-right text-xs text-primary">
                      {q.error}
                    </td>
                  ) : (
                    <>
                      <td className="py-1 text-right font-semibold text-primary">{formatMoney(q.price)}</td>
                      <td className="py-1 text-right text-xs text-muted">lucro {formatMoney(q.net_profit)}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {quote.quotes.length === 0 && <p className="text-xs text-muted">Cadastre tarifas para ver o preço por canal.</p>}
          {quote.warnings.map((w) => (
            <p key={w} className="mt-1 text-xs text-primary">
              {w}
            </p>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-xs text-muted">{quote.reason}</p>
      )}
    </div>
  );
}
