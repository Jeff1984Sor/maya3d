import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { AdminApiError, adminApi } from "@/lib/admin-api";
import { SESSION_COOKIE, sessionSecret, verifySession } from "@/lib/session";

export const dynamic = "force-dynamic";

/** Andamento da foto → objeto 3D (IA), para o navegador acompanhar sem ver o token da API. */
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await verifySession(sessionSecret(), (await cookies()).get(SESSION_COOKIE)?.value))) {
    return NextResponse.json({ error: "não autenticado" }, { status: 401 });
  }
  const { id } = await params;
  if (!/^[a-f0-9]{32}$/.test(id)) return NextResponse.json({ error: "id inválido" }, { status: 400 });
  try {
    return NextResponse.json(await adminApi(`/photo3d/${id}`, { signal: AbortSignal.timeout(30_000) }));
  } catch (error) {
    // demorou: a IA/finalização segue no servidor; o painel só consulta de novo
    if (error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError")) {
      return NextResponse.json({ id, status: "processando", progress: 0 });
    }
    const status = error instanceof AdminApiError ? error.status : 502;
    return NextResponse.json({ error: error instanceof Error ? error.message : "falha" }, { status });
  }
}
