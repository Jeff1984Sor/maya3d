import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { AdminApiError, api } from "@/lib/admin-api";
import { SESSION_COOKIE, sessionSecret, verifySession } from "@/lib/session";

export const dynamic = "force-dynamic";

/** Status de um job da fila, para o navegador acompanhar sem ver o token da API. */
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await verifySession(sessionSecret(), (await cookies()).get(SESSION_COOKIE)?.value))) {
    return NextResponse.json({ error: "não autenticado" }, { status: 401 });
  }
  const { id } = await params;
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) return NextResponse.json({ error: "id inválido" }, { status: 400 });
  try {
    return NextResponse.json(await api.get(`/jobs/${id}`));
  } catch (error) {
    const status = error instanceof AdminApiError ? error.status : 502;
    return NextResponse.json({ error: error instanceof Error ? error.message : "falha" }, { status });
  }
}
