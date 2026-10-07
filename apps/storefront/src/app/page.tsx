import { api } from "@/lib/api";

export const revalidate = 30;

export default async function Home() {
  const [brand, ready] = await Promise.all([api.getBrandOrFallback(), api.getReadyOrNull()]);
  const online = ready?.status === "ok";

  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col justify-center gap-8 px-6 py-16">
      <span
        className={`inline-flex w-fit items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-sm ${
          online ? "text-secondary" : "text-muted"
        }`}
      >
        <span aria-hidden className={`size-2 rounded-full ${online ? "bg-secondary" : "bg-muted"}`} />
        {online ? "Sistema no ar" : "Sistema iniciando"}
      </span>

      <h1 className="font-heading text-5xl font-bold tracking-tight">{brand.name}</h1>
      {brand.tagline && <p className="text-xl text-muted">{brand.tagline}</p>}

      <div>
        <a
          href="#"
          className="inline-block rounded-xl bg-primary px-6 py-3 font-medium text-white transition hover:opacity-90"
        >
          Em breve: catálogo
        </a>
      </div>
    </main>
  );
}
