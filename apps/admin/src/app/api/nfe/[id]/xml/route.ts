import { cookies } from "next/headers";
import { SESSION_COOKIE, sessionSecret, verifySession } from "@/lib/session";

export const dynamic = "force-dynamic";

/** Download do XML da NF-e (nfeProc). O token da API fica no servidor. */
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await verifySession(sessionSecret(), (await cookies()).get(SESSION_COOKIE)?.value))) {
    return Response.json({ detail: "não autenticado" }, { status: 401 });
  }
  const { id } = await params;
  if (!/^\d{1,10}$/.test(id)) return Response.json({ detail: "nota inválida" }, { status: 400 });
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const upstream = await fetch(`${base}/v1/admin/nfe/${id}/xml`, {
    headers: { "x-admin-token": process.env.ADMIN_API_TOKEN ?? "" },
    cache: "no-store",
  });
  return new Response(await upstream.arrayBuffer(), {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/xml",
      "content-disposition": upstream.headers.get("content-disposition") ?? "attachment",
    },
  });
}
