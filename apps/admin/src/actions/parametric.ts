"use server";

import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

export type StartResult = { jobId?: string; error?: string };

export async function startGeneration(slug: string, params: Record<string, unknown>): Promise<StartResult> {
  await requireSession();
  try {
    const { job_id } = await api.post<{ job_id: string }>(`/parametric/${encodeURIComponent(slug)}/generate`, params);
    return { jobId: job_id };
  } catch (error) {
    return { error: error instanceof AdminApiError ? error.message : "Falha ao enviar para geração." };
  }
}
