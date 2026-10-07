import { imageAction, uploadProductImages, type ProductImage } from "@/actions/content";
import { Badge, Button, Card } from "@/components/ui";

/** Fotos do produto: a primeira é a capa na loja. */
export function ProductImages({ productId, images }: { productId: number; images: ProductImage[] }) {
  return (
    <Card title="📷 Fotos">
      {images.length === 0 && <p className="mb-3 text-sm text-muted">Sem fotos: a loja mostra um ícone no lugar. Envie ao menos uma.</p>}
      {images.length > 0 && (
        <div className="mb-4 grid grid-cols-3 gap-2">
          {images.map((img, i) => (
            <div key={img.id} className="overflow-hidden rounded-xl border border-border">
              {/* eslint-disable-next-line @next/next/no-img-element -- miniatura pelo proxy do painel */}
              <img src={`/api/files/${img.thumb_key}`} alt="" className="aspect-square w-full bg-white object-cover" />
              <div className="flex items-center justify-between gap-1 p-1 text-xs">
                {i === 0 ? (
                  <Badge tone="ok">capa</Badge>
                ) : (
                  <form action={imageAction.bind(null, productId, img.id, "cover")}>
                    <button className="text-secondary hover:underline">capa</button>
                  </form>
                )}
                <form action={imageAction.bind(null, productId, img.id, "delete")}>
                  <button className="text-primary hover:underline">remover</button>
                </form>
              </div>
            </div>
          ))}
        </div>
      )}
      <form action={uploadProductImages.bind(null, productId)} className="flex flex-col gap-2">
        <input type="file" name="files" multiple accept="image/png,image/jpeg,image/webp" className="text-sm" />
        <Button variant="secondary">Enviar fotos</Button>
        <p className="text-xs text-muted">JPG, PNG ou WebP até 20 MB. O sistema otimiza e tira os dados de localização da foto.</p>
      </form>
    </Card>
  );
}
