"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { AdminApiError, adminApi, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

function go(path: string, kind: "ok" | "erro", msg: string): never {
  redirect(`${path}${path.includes("?") ? "&" : "?"}${kind}=${encodeURIComponent(msg)}`);
}

function message(error: unknown): string {
  return error instanceof AdminApiError ? error.message : "Falha ao falar com a API.";
}

/** Certificado A1 (.pfx) + senha: vai direto para a API, que confere e guarda cifrado. */
export async function uploadCertificate(form: FormData): Promise<void> {
  await requireSession();
  const file = form.get("file");
  const senha = String(form.get("senha") ?? "");
  if (!(file instanceof File) || file.size === 0) go("/nota-fiscal", "erro", "Escolha o arquivo do certificado (.pfx).");
  if (!senha) go("/nota-fiscal", "erro", "Digite a senha do certificado.");
  const body = new FormData();
  body.set("file", file, "certificado.pfx");
  body.set("senha", senha);
  let titular = "";
  try {
    ({ titular } = await adminApi<{ titular: string }>("/fiscal/certificate", { method: "POST", body }));
  } catch (error) {
    go("/nota-fiscal", "erro", message(error));
  }
  revalidatePath("/nota-fiscal");
  go("/nota-fiscal", "ok", `Certificado de ${titular} guardado (cifrado).`);
}

export async function testSefaz(): Promise<void> {
  await requireSession();
  let r: { cstat: string; motivo: string; online: boolean };
  try {
    r = await api.post("/fiscal/sefaz-status", {});
  } catch (error) {
    go("/nota-fiscal", "erro", message(error));
  }
  go("/nota-fiscal", r.online ? "ok" : "erro", `SEFAZ respondeu: ${r.cstat} — ${r.motivo}`);
}

const FIELDS = ["nome", "documento", "email", "ie", "cep", "logradouro", "numero", "complemento", "bairro", "municipio", "uf", "cod_municipio"] as const;

export async function emitNfe(orderId: number, form: FormData): Promise<void> {
  await requireSession();
  const back = `/pedidos/${orderId}`;
  const recipient: Record<string, string | null> = {};
  for (const f of FIELDS) {
    const v = String(form.get(f) ?? "").trim();
    recipient[f] = v || (f === "email" || f === "ie" || f === "complemento" ? null : "");
  }
  let r: { number: number; status: string; motivo: string | null; cstat: string | null };
  try {
    r = await api.post(`/orders/${orderId}/nfe`, { recipient });
  } catch (error) {
    go(back, "erro", message(error));
  }
  revalidatePath(back);
  if (r.status === "autorizada") go(back, "ok", `NF-e nº ${r.number} autorizada.`);
  go(back, "erro", `NF-e nº ${r.number}: ${r.status} — ${r.cstat ?? ""} ${r.motivo ?? ""}`);
}

export async function consultNfe(invoiceId: number, back: string): Promise<void> {
  await requireSession();
  let r: { number: number; status: string; motivo: string | null };
  try {
    r = await api.post(`/nfe/${invoiceId}/consult`, {});
  } catch (error) {
    go(back, "erro", message(error));
  }
  revalidatePath(back);
  go(back, r.status === "autorizada" ? "ok" : "erro", `NF-e nº ${r.number}: ${r.status} — ${r.motivo ?? ""}`);
}

export async function resendNfe(invoiceId: number, back: string): Promise<void> {
  await requireSession();
  let r: { email_status: string | null; ml_status: string | null };
  try {
    r = await api.post(`/nfe/${invoiceId}/resend`, {});
  } catch (error) {
    go(back, "erro", message(error));
  }
  revalidatePath(back);
  go(back, "ok", [r.ml_status, r.email_status].filter(Boolean).join(" · ") || "Reenviado.");
}

export async function cancelNfe(invoiceId: number, back: string, form: FormData): Promise<void> {
  await requireSession();
  const justificativa = String(form.get("justificativa") ?? "").trim();
  try {
    await api.post(`/nfe/${invoiceId}/cancel`, { justificativa });
  } catch (error) {
    go(back, "erro", message(error));
  }
  revalidatePath(back);
  go(back, "ok", "Nota cancelada na SEFAZ.");
}
