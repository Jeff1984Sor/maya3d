export const dynamic = "force-dynamic";

/** Proxy da prévia 3D (só STL de prévias paramétricas). */
export async function GET(_req: Request, { params }: { params: Promise<{ job: string; file: string }> }) {
  const { job, file } = await params;
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(job) || !/^[A-Za-z0-9_-]{1,40}\.stl$/.test(file)) {
    return new Response("inválido", { status: 400 });
  }
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const upstream = await fetch(`${base}/v1/store/files/parametric/${job}/${file}`, { cache: "no-store" });
  if (!upstream.ok || !upstream.body) return new Response("não encontrado", { status: upstream.status });
  return new Response(upstream.body, { headers: { "content-type": "model/stl", "cache-control": "public, max-age=3600" } });
}
