/** Prévia 3D leve do produto (para girar e trocar de cor). Repassa da API com cache. */
export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!/^[a-z0-9-]{1,220}$/.test(slug)) return new Response("não encontrado", { status: 404 });
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const upstream = await fetch(`${base}/v1/store/products/${slug}/preview.stl`, { cache: "no-store" });
  if (!upstream.ok || !upstream.body) return new Response("não encontrado", { status: 404 });
  return new Response(upstream.body, {
    headers: { "content-type": "model/stl", "cache-control": "public, max-age=86400" },
  });
}
