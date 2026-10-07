import { cookies } from "next/headers";
import { SESSION_COOKIE, sessionSecret, verifySession } from "@/lib/session";

export const dynamic = "force-dynamic";

/** Proxy autenticado dos arquivos gerados (STL), para visualizar e baixar no painel. */
export async function GET(_req: Request, { params }: { params: Promise<{ key: string[] }> }) {
  if (!(await verifySession(sessionSecret(), (await cookies()).get(SESSION_COOKIE)?.value))) {
    return new Response("não autenticado", { status: 401 });
  }
  const { key } = await params;
  if (key.some((part) => !/^[A-Za-z0-9._-]+$/.test(part) || part === "." || part === "..")) {
    return new Response("caminho inválido", { status: 400 });
  }
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const upstream = await fetch(`${base}/v1/admin/files/${key.join("/")}`, {
    headers: { "x-admin-token": process.env.ADMIN_API_TOKEN ?? "" },
    cache: "no-store",
  });
  if (!upstream.ok || !upstream.body) return new Response("arquivo não encontrado", { status: upstream.status });
  return new Response(upstream.body, {
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "content-disposition": upstream.headers.get("content-disposition") ?? "attachment",
      "cache-control": "private, max-age=3600",
    },
  });
}
