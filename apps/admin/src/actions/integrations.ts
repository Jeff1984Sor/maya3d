"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

export type IntegrationField = {
  key: string;
  group: "ia" | "whatsapp";
  label: string;
  secret: boolean;
  hint: string;
  choices: string[];
  configured: boolean;
  source: "painel" | "servidor" | null;
  preview: string | null;
  generatable: boolean;
};

const back = (key: "ok" | "erro", msg: string): never => redirect(`/integracoes?${key}=${encodeURIComponent(msg)}`);
const errMsg = (error: unknown, fallback: string) => (error instanceof AdminApiError ? error.message : fallback);

/** Salva só o que foi preenchido: campo vazio mantém o valor atual (segredos nunca voltam ao navegador). */
export async function saveIntegrations(keys: string[], form: FormData): Promise<void> {
  await requireSession();
  const values: Record<string, string> = {};
  for (const k of keys) {
    const v = String(form.get(k) ?? "").trim();
    if (v) values[k] = v;
  }
  try {
    await api.put("/integrations", { values, clear: [] });
  } catch (error) {
    back("erro", errMsg(error, "Falha ao salvar."));
  }
  revalidatePath("/integracoes");
  revalidatePath("/ia");
  revalidatePath("/mensagens");
  back("ok", Object.keys(values).length ? "Salvo. Já está valendo, sem reiniciar nada." : "Nada mudou.");
}

export async function clearIntegration(key: string): Promise<void> {
  await requireSession();
  try {
    await api.put("/integrations", { values: {}, clear: [key] });
  } catch (error) {
    back("erro", errMsg(error, "Falha ao remover."));
  }
  revalidatePath("/integracoes");
  back("ok", "Removido do painel.");
}

export async function generateIntegration(key: string): Promise<void> {
  await requireSession();
  try {
    await api.post(`/integrations/${key}/generate`, {});
  } catch (error) {
    back("erro", errMsg(error, "Falha ao gerar."));
  }
  revalidatePath("/integracoes");
  back("ok", "Gerado. Copie e cole o mesmo valor na Meta.");
}

export async function testWhatsapp(): Promise<void> {
  await requireSession();
  let result: { status: string; error: string | null } | null = null;
  try {
    result = await api.post<{ status: string; error: string | null }>("/integrations/whatsapp/test", {});
  } catch (error) {
    back("erro", errMsg(error, "Falha no teste."));
  }
  if (result?.status === "enviado") back("ok", "Mensagem de teste enviada para o seu WhatsApp.");
  back("erro", `A Meta recusou: ${result?.error ?? "erro desconhecido"}`);
}
