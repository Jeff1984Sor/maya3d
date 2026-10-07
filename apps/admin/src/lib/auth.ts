import "server-only";
import { createHash, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE, SESSION_TTL_SECONDS, sessionSecret, signSession, verifySession } from "./session";

// Trava contra força bruta: depois de N erros, bloqueia o login por um tempo (processo único).
const MAX_FAILURES = 10;
const LOCK_MS = 15 * 60 * 1000;
const failures = { count: 0, lockedUntil: 0 };

export type LoginResult = { error?: string };

function samePassword(given: string, expected: string): boolean {
  const a = createHash("sha256").update(given).digest();
  const b = createHash("sha256").update(expected).digest();
  return timingSafeEqual(a, b);
}

export async function attemptLogin(password: string): Promise<LoginResult> {
  const expected = process.env.ADMIN_PASSWORD;
  const secret = sessionSecret();
  if (!expected || !secret) {
    return { error: "Painel sem senha configurada no servidor (ADMIN_PASSWORD)." };
  }
  if (Date.now() < failures.lockedUntil) {
    return { error: "Muitas tentativas. Aguarde 15 minutos." };
  }
  if (!samePassword(password, expected)) {
    failures.count += 1;
    if (failures.count >= MAX_FAILURES) {
      failures.lockedUntil = Date.now() + LOCK_MS;
      failures.count = 0;
    }
    return { error: "Senha incorreta." };
  }
  failures.count = 0;
  (await cookies()).set(SESSION_COOKIE, await signSession(secret), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.ADMIN_COOKIE_SECURE === "true", // true quando houver HTTPS
    maxAge: SESSION_TTL_SECONDS,
    path: "/",
  });
  return {};
}

export async function logout(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
}

/** Defesa em profundidade: além do middleware, cada página do painel confere a sessão. */
export async function requireSession(): Promise<void> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!(await verifySession(sessionSecret(), token))) redirect("/login");
}
