"use client";

import { StlViewer } from "@print3d/shared/stl-viewer";
import { useState, type ReactNode } from "react";
import type { Product } from "@/lib/store";
import { BuyBox } from "./buy-box";
import { Gallery } from "./gallery";

/**
 * Fotos + "Ver em 3D" à esquerda, compra à direita. A cor escolhida na compra pinta a peça 3D
 * na hora (a foto é da amostra e não muda de cor).
 */
export function ProductView({
  product,
  fallback,
  header,
  footer,
}: {
  product: Product;
  fallback: string;
  header: ReactNode;
  footer: ReactNode;
}) {
  const first = product.variants.find((v) => v.price_pix) ?? product.variants[0];
  const [colorId, setColorId] = useState<number | undefined>(first?.colors[0]?.material_id);
  const [view, setView] = useState<"fotos" | "3d">("fotos");
  const hex =
    product.variants.flatMap((v) => v.colors).find((c) => c.material_id === colorId)?.hex ?? "#d4d4d8";

  return (
    <>
      <div className="space-y-3">
        {product.model3d && (
          <div className="flex gap-2 text-sm">
            {(["fotos", "3d"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`rounded-full border px-4 py-1.5 ${view === v ? "border-ink bg-ink text-bg" : "border-border"}`}
              >
                {v === "fotos" ? "Fotos" : "🔄 Ver em 3D na cor escolhida"}
              </button>
            ))}
          </div>
        )}
        {view === "3d" && product.model3d ? (
          <div className="space-y-2">
            <StlViewer
              url={`/api/3d/${encodeURIComponent(product.slug)}`}
              color={hex}
              className="relative aspect-square w-full overflow-hidden rounded-3xl border border-border bg-white"
            />
            <p className="text-center text-xs text-muted">Arraste para girar · troque a cor ao lado e veja na hora</p>
          </div>
        ) : (
          <Gallery images={product.images ?? []} fallback={fallback} title={product.title} />
        )}
      </div>
      <div className="space-y-6">
        {header}
        <BuyBox
          product={product}
          colorId={colorId}
          onColorChange={(id) => {
            setColorId(id);
            if (product.model3d) setView("3d"); // escolheu a cor: mostra a peça nela
          }}
        />
        {footer}
      </div>
    </>
  );
}
