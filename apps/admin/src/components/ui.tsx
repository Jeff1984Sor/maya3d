import type { ComponentProps, ReactNode } from "react";

/** Componentes visuais do painel. Só tokens da marca (bg, surface, ink, muted, primary, secondary, border). */

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function PageHeader({ title, description, children }: { title: string; description?: string; children?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-heading text-2xl font-bold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {children}
    </header>
  );
}

export function Card({ title, children, className }: { title?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-2xl border border-border bg-surface p-5", className)}>
      {title && <h2 className="mb-4 font-heading text-base font-semibold">{title}</h2>}
      {children}
    </section>
  );
}

const buttonStyles = {
  primary: "bg-primary text-white hover:opacity-90",
  secondary: "border border-border bg-surface hover:bg-bg",
  danger: "border border-primary/40 text-primary hover:bg-primary/10",
} as const;

export function Button({
  variant = "primary",
  className,
  ...props
}: ComponentProps<"button"> & { variant?: keyof typeof buttonStyles }) {
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition disabled:opacity-50",
        buttonStyles[variant],
        className,
      )}
      {...props}
    />
  );
}

export const inputClass =
  "w-full rounded-xl border border-border bg-bg px-3 py-2 text-sm outline-none focus:border-secondary focus:ring-2 focus:ring-secondary/20";

export function Label({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted">{hint}</span>}
    </label>
  );
}

export function Badge({ tone = "muted", children }: { tone?: "ok" | "danger" | "muted" | "warn"; children: ReactNode }) {
  const tones = {
    ok: "bg-secondary/15 text-secondary",
    danger: "bg-primary/15 text-primary",
    warn: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
    muted: "bg-border text-muted",
  };
  return <span className={cx("inline-flex rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>{children}</span>;
}

export function Alert({ tone, children }: { tone: "ok" | "error"; children: ReactNode }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cx(
        "mb-4 rounded-xl border px-4 py-3 text-sm",
        tone === "ok" ? "border-secondary/40 bg-secondary/10" : "border-primary/40 bg-primary/10",
      )}
    >
      {children}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted">{children}</p>;
}
