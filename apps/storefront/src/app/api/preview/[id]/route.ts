import { NextResponse } from "next/server";
import { storeApi } from "@/lib/store";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) return NextResponse.json({ status: "desconhecido" }, { status: 400 });
  try {
    return NextResponse.json(await storeApi(`/jobs/${id}`));
  } catch {
    return NextResponse.json({ status: "falhou" }, { status: 502 });
  }
}
