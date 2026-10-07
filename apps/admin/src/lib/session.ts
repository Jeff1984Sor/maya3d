/**
 * Sessão do painel: cookie "<expira>.<assinatura>" com HMAC-SHA256.
 * Usa Web Crypto para rodar igual no middleware (edge) e no servidor (node).
 */

export const SESSION_COOKIE = "p3d_admin";
export const SESSION_TTL_SECONDS = 12 * 60 * 60;

const encoder = new TextEncoder();

function toBase64Url(bytes: ArrayBuffer): string {
  let binary = "";
  for (const b of new Uint8Array(bytes)) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function hmac(secret: string, message: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return toBase64Url(await crypto.subtle.sign("HMAC", key, encoder.encode(message)));
}

/** Comparação em tempo constante (não vaza em quantos caracteres a assinatura bate). */
function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function signSession(secret: string, nowSeconds = Math.floor(Date.now() / 1000)) {
  const expires = nowSeconds + SESSION_TTL_SECONDS;
  return `${expires}.${await hmac(secret, `admin|${expires}`)}`;
}

export async function verifySession(
  secret: string | undefined,
  token: string | undefined,
  nowSeconds = Math.floor(Date.now() / 1000),
): Promise<boolean> {
  if (!secret || !token) return false;
  const [expiresRaw, signature] = token.split(".");
  const expires = Number(expiresRaw);
  if (!signature || !Number.isInteger(expires) || expires <= nowSeconds) return false;
  return safeEqual(signature, await hmac(secret, `admin|${expires}`));
}

/** Segredo da sessão: variável própria ou, na falta, o token da API (ambos secretos). */
export function sessionSecret(): string | undefined {
  return process.env.ADMIN_SESSION_SECRET || process.env.ADMIN_API_TOKEN || undefined;
}
