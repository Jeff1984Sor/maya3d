"use server";

import { AdminApiError, adminApi } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

export type AgentTurn = { role: "user" | "assistant"; content: string };
export type ImageCard = { number: number; id: string; title: string; thumbnail: string; creator: string; license: string; source_page: string };
export type Proposal = { id: string; tool: string; summary: string };
export type JobCard = { job: string; title: string };
export type AgentReply = { reply: string; memo: string; images: ImageCard[]; proposals: Proposal[]; jobs: JobCard[] };
export type ConfirmResult = { message: string; job: string | null; product_id: number | null };

// várias ferramentas (e o código de uma peça) numa resposta: bem mais que os 15 s padrão
const SLOW = 150_000;

function post<T>(path: string, data: unknown): Promise<T> {
  return adminApi<T>(path, { method: "POST", body: JSON.stringify(data), signal: AbortSignal.timeout(SLOW) });
}

export async function askAgent(turns: AgentTurn[]): Promise<AgentReply | { error: string }> {
  await requireSession();
  try {
    return await post<AgentReply>("/agent/chat", { turns: turns.slice(-40) });
  } catch (error) {
    return { error: error instanceof AdminApiError ? error.message : "Falha ao falar com o assistente." };
  }
}

export async function confirmProposal(id: string): Promise<ConfirmResult | { error: string }> {
  await requireSession();
  if (!/^[a-f0-9]{16}$/.test(id)) return { error: "Proposta inválida." };
  try {
    return await post<ConfirmResult>(`/agent/proposals/${id}/confirm`, {});
  } catch (error) {
    return { error: error instanceof AdminApiError ? error.message : "Falha ao confirmar." };
  }
}
