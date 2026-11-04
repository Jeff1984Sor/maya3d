"use server";

import { AdminApiError, adminApi } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

const MODES = ["litofania", "placa_multicor", "cortador", "chaveiro_silhueta", "objeto_3d"] as const;
const NUMBER_FIELDS = ["width_mm", "size_mm", "min_mm", "max_mm", "frame_mm", "colors", "thickness_mm", "height_mm"];

/** jobId com prefixo "ia:" = objeto 3D pela IA (andamento em /api/photo3d, não na fila). */
export async function startPhoto(form: FormData): Promise<{ jobId?: string; error?: string }> {
  await requireSession();
  const mode = String(form.get("mode") ?? "");
  if (!MODES.includes(mode as (typeof MODES)[number])) return { error: "Modo inválido." };
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "Escolha uma foto." };
  const body = new FormData();
  body.append("file", file, file.name);
  if (mode === "objeto_3d") {
    const size = String(form.get("size_mm") ?? "").replace(",", ".").trim();
    if (size) body.append("size_mm", size);
    try {
      const { id } = await adminApi<{ id: string }>("/photo3d", { method: "POST", body });
      return { jobId: `ia:${id}` };
    } catch (error) {
      return { error: error instanceof AdminApiError ? error.message : "Falha ao enviar a foto." };
    }
  }
  for (const key of NUMBER_FIELDS) {
    const value = String(form.get(key) ?? "").replace(",", ".").trim();
    if (value) body.append(key, value);
  }
  body.append("invert", form.get("invert") === "on" ? "true" : "false");
  try {
    const { job_id } = await adminApi<{ job_id: string }>(`/photo/${mode}`, { method: "POST", body });
    return { jobId: job_id };
  } catch (error) {
    return { error: error instanceof AdminApiError ? error.message : "Falha ao enviar a foto." };
  }
}
