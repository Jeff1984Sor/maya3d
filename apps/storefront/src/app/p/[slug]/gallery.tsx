"use client";

import { useState } from "react";
import type { StoreImage } from "@/lib/store";

/** Fotos do produto: imagem grande + miniaturas. Sem fotos: o emoji do nicho. */
export function Gallery({ images, fallback, title }: { images: StoreImage[]; fallback: string; title: string }) {
  const [current, setCurrent] = useState(0);
  if (!images.length) {
    return (
      <div className="flex aspect-square items-center justify-center rounded-3xl border border-border bg-white text-[9rem]">{fallback}</div>
    );
  }
  const main = images[Math.min(current, images.length - 1)]!;
  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-3xl border border-border bg-white">
        {/* eslint-disable-next-line @next/next/no-img-element -- WebP otimizado pela API */}
        <img src={main.url} alt={main.alt ?? title} className="aspect-square w-full object-contain" />
      </div>
      {images.length > 1 && (
        <div className="flex gap-2 overflow-x-auto">
          {images.map((img, i) => (
            <button
              key={img.thumb}
              onClick={() => setCurrent(i)}
              className={`size-20 shrink-0 overflow-hidden rounded-xl border-2 ${i === current ? "border-secondary" : "border-border"}`}
              aria-label={`Foto ${i + 1}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- miniatura WebP */}
              <img src={img.thumb} alt="" className="h-full w-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
