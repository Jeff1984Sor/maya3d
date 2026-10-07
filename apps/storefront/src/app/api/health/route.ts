import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({ status: "ok", app: "storefront", release: process.env.RELEASE ?? "dev" });
}
