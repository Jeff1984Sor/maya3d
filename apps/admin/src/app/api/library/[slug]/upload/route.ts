import { cookies } from "next/headers";
import { SESSION_COOKIE, sessionSecret, verifySession } from "@/lib/session";

export const dynamic = "force-dynamic";

/**
 * Envio de arquivo da Biblioteca (ZIP/STL de centenas de MB): repassa o corpo em fluxo para a
 * API, sem passar pelo limite das server actions. Fica fora do middleware (que limita o corpo),
 * então confere a sessão aqui.
 */
export async function POST(req: Request, { params }: { params: Promise<{ slug: string }> }) {
  if (!(await verifySession(sessionSecret(), (await cookies()).get(SESSION_COOKIE)?.value))) {
    return Response.json({ detail: "não autenticado" }, { status: 401 });
  }
  const { slug } = await params;
  if (!/^[a-z0-9-]{1,80}$/.test(slug)) return Response.json({ detail: "coleção inválida" }, { status: 400 });
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const upstream = await fetch(`${base}/v1/admin/library/collections/${slug}/files`, {
    method: "POST",
    body: req.body,
    headers: {
      "content-type": req.headers.get("content-type") ?? "application/octet-stream",
      "x-admin-token": process.env.ADMIN_API_TOKEN ?? "",
    },
    // @ts-expect-error -- necessário no Node para enviar corpo em fluxo
    duplex: "half",
  });
  const body = await upstream.text();
  return new Response(body, { status: upstream.status, headers: { "content-type": "application/json" } });
}
