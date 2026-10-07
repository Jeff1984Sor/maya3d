import { cookies } from "next/headers";
import { SESSION_COOKIE, sessionSecret, verifySession } from "@/lib/session";

export const dynamic = "force-dynamic";

/**
 * Envio de foto do produto (uma por chamada, com progresso no navegador). Repassa o corpo em
 * fluxo para a API; fica fora do middleware (que limita o corpo), então confere a sessão aqui.
 */
export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await verifySession(sessionSecret(), (await cookies()).get(SESSION_COOKIE)?.value))) {
    return Response.json({ detail: "não autenticado" }, { status: 401 });
  }
  const { id } = await params;
  if (!/^\d{1,10}$/.test(id)) return Response.json({ detail: "produto inválido" }, { status: 400 });
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const upstream = await fetch(`${base}/v1/admin/products/${id}/images`, {
    method: "POST",
    body: req.body,
    headers: {
      "content-type": req.headers.get("content-type") ?? "application/octet-stream",
      "x-admin-token": process.env.ADMIN_API_TOKEN ?? "",
    },
    // @ts-expect-error -- necessário no Node para enviar corpo em fluxo
    duplex: "half",
  });
  return new Response(await upstream.text(), { status: upstream.status, headers: { "content-type": "application/json" } });
}
