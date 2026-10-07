"use server";

import { StoreApiError, storeApi } from "@/lib/store";

export async function requestPreview(model: string, params: Record<string, unknown>): Promise<{ jobId?: string; error?: string }> {
  if (!/^[a-z0-9-]{1,60}$/.test(model)) return { error: "modelo inválido" };
  try {
    const { job_id } = await storeApi<{ job_id: string }>(`/parametric/${model}/preview`, {
      method: "POST",
      body: JSON.stringify(params),
    });
    return { jobId: job_id };
  } catch (error) {
    return { error: error instanceof StoreApiError ? error.message : "Não foi possível gerar agora." };
  }
}
