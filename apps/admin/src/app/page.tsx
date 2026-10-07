import { api } from "@/lib/api";

export const revalidate = 30;

export default async function AdminHome() {
  const [brand, ready] = await Promise.all([api.getBrandOrFallback(), api.getReadyOrNull()]);
  const checks = Object.entries(ready?.checks ?? {});

  return (
    <main className="mx-auto max-w-3xl space-y-8 px-6 py-16">
      <header>
        <p className="text-sm uppercase tracking-widest text-muted">Painel</p>
        <h1 className="font-heading text-4xl font-bold tracking-tight">{brand.name}</h1>
      </header>

      <section className="rounded-2xl border border-border bg-surface p-6">
        <h2 className="mb-4 font-heading text-lg font-semibold">Saúde do sistema</h2>
        {checks.length === 0 ? (
          <p className="text-muted">API indisponível no momento.</p>
        ) : (
          <ul className="space-y-2">
            {checks.map(([name, check]) => (
              <li key={name} className="flex items-center justify-between">
                <span className="capitalize">{name}</span>
                <span className={check.ok ? "text-secondary" : "text-primary"}>
                  {check.ok ? "ok" : `falha (${check.detail})`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
