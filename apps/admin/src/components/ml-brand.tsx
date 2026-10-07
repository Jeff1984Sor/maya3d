import type { ReactNode } from "react";

/** Cores do Mercado Livre, só para identificar a integração dentro do painel. */
const YELLOW = "#FFE600";
const NAVY = "#2D3277";

/** Selo "Mercado Livre": aperto de mãos (símbolo da marca) em amarelo e marinho. */
export function MlLogo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Mercado Livre">
      <circle cx="32" cy="32" r="31" fill={YELLOW} stroke={NAVY} strokeWidth="2" />
      <ellipse cx="32" cy="33" rx="22" ry="14" fill="#fff" stroke={NAVY} strokeWidth="2.5" />
      {/* duas mãos se apertando, em traço simples */}
      <path
        d="M14 32 l8-5 c3-2 6-2 9 0 l3 2 c2 1 2 3 0 4 l-1 1 M50 32 l-8-5 c-3-2-6-2-9 0 M22 34 l6 5 c1 1 3 1 4 0 M27 36 l5 4 c1 1 3 1 4 0 M32 37 l4 3 c1 1 3 1 4 0 l4-4"
        fill="none"
        stroke={NAVY}
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Faixa de cabeçalho com a identidade do Mercado Livre. */
export function MlHero({ title, subtitle, children }: { title: string; subtitle: string; children?: ReactNode }) {
  return (
    <div
      className="mb-6 flex flex-wrap items-center gap-4 overflow-hidden rounded-2xl p-5 shadow-sm"
      style={{ background: `linear-gradient(120deg, ${YELLOW} 0%, #FFF159 60%, #FFF8B8 100%)`, color: NAVY }}
    >
      <div className="rounded-full bg-white/60 p-1 shadow">
        <MlLogo size={56} />
      </div>
      <div className="min-w-0 flex-1">
        <h1 className="font-heading text-2xl font-extrabold tracking-tight">{title}</h1>
        <p className="text-sm opacity-80">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

/** Título de card com o selo pequeno. */
export function MlTitle({ children }: { children: ReactNode }) {
  return (
    <span className="flex items-center gap-2">
      <MlLogo size={22} />
      {children}
    </span>
  );
}

export const ML_COLORS = { yellow: YELLOW, navy: NAVY };
