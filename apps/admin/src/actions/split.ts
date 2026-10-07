"use server";

import { AdminApiError, adminApi } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

export type SplitStart = { jobId?: string; error?: string };

/** Envia o STL para a API, que guarda o arquivo e põe a divisão na fila do worker. */
export async function startSplit(form: FormData): Promise<SplitStart> {
  await requireSession();
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "Escolha um arquivo STL." };
  const body = new FormData();
  body.append("file", file, file.name);
  for (const key of ["printer_id", "pin_diameter_mm", "clearance_mm", "margin_mm"]) {
    const value = String(form.get(key) ?? "").replace(",", ".");
    if (value) body.append(key, value);
  }
  try {
    const { job_id } = await adminApi<{ job_id: string }>("/mesh/split", { method: "POST", body });
    return { jobId: job_id };
  } catch (error) {
    return { error: error instanceof AdminApiError ? error.message : "Falha ao enviar o arquivo." };
  }
}
