import type { ReactNode } from "react";

/** Cor da Shopee, só para identificar a integração dentro do painel. */
const ORANGE = "#EE4D2D";

/** Selo "Shopee": sacola de compras laranja com a letra S. */
export function ShopeeLogo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Shopee">
      <path d="M22 20 a10 10 0 0 1 20 0" fill="none" stroke={ORANGE} strokeWidth="4" strokeLinecap="round" />
      <path d="M10 20 h44 l-3 34 a6 6 0 0 1-6 5 H19 a6 6 0 0 1-6-5 Z" fill={ORANGE} />
      <text x="32" y="48" textAnchor="middle" fontSize="26" fontWeight="800" fill="#fff" fontFamily="system-ui, sans-serif">
        S
      </text>
    </svg>
  );
}

export function ShopeeHero({ title, subtitle, children }: { title: string; subtitle: string; children?: ReactNode }) {
  return (
    <div
      className="mb-6 flex flex-wrap items-center gap-4 overflow-hidden rounded-2xl p-5 text-white shadow-sm"
      style={{ background: `linear-gradient(120deg, ${ORANGE} 0%, #F5663F 55%, #FF8A65 100%)` }}
    >
      <div className="rounded-2xl bg-white p-2 shadow">
        <ShopeeLogo size={52} />
      </div>
      <div className="min-w-0 flex-1">
        <h1 className="font-heading text-2xl font-extrabold tracking-tight">{title}</h1>
        <p className="text-sm opacity-90">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

export function ShopeeTitle({ children }: { children: ReactNode }) {
  return (
    <span className="flex items-center gap-2">
      <ShopeeLogo size={22} />
      {children}
    </span>
  );
}

export const SHOPEE_COLOR = ORANGE;
