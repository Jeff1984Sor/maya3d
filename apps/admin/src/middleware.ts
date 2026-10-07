import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, sessionSecret, verifySession } from "@/lib/session";

/** Todo o painel exige sessão, exceto login e healthcheck. O envio da Biblioteca confere a
 * sessão na própria rota (o middleware limitaria o tamanho do corpo). */
export async function middleware(request: NextRequest) {
  const ok = await verifySession(sessionSecret(), request.cookies.get(SESSION_COOKIE)?.value);
  if (ok) return NextResponse.next();
  const login = new URL("/login", request.url);
  login.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!login|api/health|api/library|_next/static|_next/image|favicon.ico).*)"],
};
