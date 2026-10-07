/** Imagens públicas da loja (fotos, logo, destaque): repassa da API com cache longo. */
export async function GET(_req: Request, { params }: { params: Promise<{ key: string[] }> }) {
  const { key } = await params;
  if (key[0] !== "media" || key.some((p) => !/^[A-Za-z0-9._-]+$/.test(p) || p === "..")) {
    return new Response("não encontrado", { status: 404 });
  }
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const upstream = await fetch(`${base}/v1/store/media/${key.join("/")}`, { cache: "no-store" });
  if (!upstream.ok || !upstream.body) return new Response("não encontrado", { status: 404 });
  return new Response(upstream.body, {
    headers: {
      "content-type": "image/webp",
      "cache-control": "public, max-age=31536000, immutable",
    },
  });
}
