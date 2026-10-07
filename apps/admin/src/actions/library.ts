"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

export type Collection = {
  slug: string;
  title: string;
  description: string | null;
  category: string;
  niche: string;
  license_text: string | null;
  status: "vazio" | "processando" | "pronto" | "erro";
  error: string | null;
  models: number;
  products: number;
  pending_files: string[];
};

export type LibraryModel = {
  id: number;
  key: string;
  title: string;
  files: { name: string; original: string; bytes: number; bbox_mm?: number[]; volume_cm3?: number; issues?: string[] }[];
  cover: string | null;
  bbox_mm: number[] | null;
  fits: boolean | null;
  issues: string[];
  status: "novo" | "produto" | "ignorado";
  product_id: number | null;
};

const msg = (error: unknown, fallback: string) => (error instanceof AdminApiError ? error.message : fallback);
const text = (f: FormData, k: string) => String(f.get(k) ?? "").trim();

export async function createCollection(form: FormData): Promise<void> {
  await requireSession();
  let slug = "";
  try {
    ({ slug } = await api.post<{ slug: string }>("/library/collections", {
      title: text(form, "title"),
      niche: text(form, "niche"),
      category: text(form, "category"),
      description: text(form, "description") || null,
      license_text: text(form, "license_text") || null,
    }));
  } catch (error) {
    redirect(`/biblioteca?erro=${encodeURIComponent(msg(error, "Falha ao criar."))}`);
  }
  revalidatePath("/biblioteca");
  redirect(`/biblioteca/${slug}?ok=${encodeURIComponent("Coleção criada. Agora envie os arquivos.")}`);
}

function back(slug: string, key: "ok" | "erro", m: string): never {
  revalidatePath(`/biblioteca/${slug}`);
  redirect(`/biblioteca/${slug}?${key}=${encodeURIComponent(m)}`);
}

export async function processCollection(slug: string): Promise<void> {
  await requireSession();
  try {
    await api.post(`/library/collections/${slug}/process`, {});
  } catch (error) {
    back(slug, "erro", msg(error, "Falha ao processar."));
  }
  back(slug, "ok", "Processando. A tela atualiza sozinha.");
}

export async function clearPending(slug: string): Promise<void> {
  await requireSession();
  try {
    await api.delete(`/library/collections/${slug}/files`);
  } catch (error) {
    back(slug, "erro", msg(error, "Falha ao descartar."));
  }
  back(slug, "ok", "Envios descartados.");
}

export async function saveLicense(slug: string, form: FormData): Promise<void> {
  await requireSession();
  let rechecked = 0;
  try {
    ({ rechecked } = await api.put<{ rechecked: number }>(`/library/collections/${slug}/license`, {
      license_text: text(form, "license_text") || null,
    }));
  } catch (error) {
    back(slug, "erro", msg(error, "Falha ao salvar a licença."));
  }
  revalidatePath("/produtos");
  back(slug, "ok", `Licença salva. ${rechecked} produto(s) verificados de novo pelo Guardião.`);
}

export async function productFromModel(slug: string, modelId: number, form: FormData): Promise<void> {
  await requireSession();
  let res: { product_id: number; guardian: string } | null = null;
  try {
    res = await api.post(`/library/models/${modelId}/product`, { title: text(form, "title") || null });
  } catch (error) {
    back(slug, "erro", msg(error, "Falha ao criar o produto."));
  }
  revalidatePath("/produtos");
  const note = res?.guardian === "bloqueado" ? " (bloqueado até a licença da coleção ser preenchida)" : "";
  redirect(`/produtos/${res!.product_id}?ok=${encodeURIComponent(`Produto criado da biblioteca${note}. Complete variantes e textos.`)}`);
}

export async function toggleIgnore(slug: string, modelId: number): Promise<void> {
  await requireSession();
  try {
    await api.post(`/library/models/${modelId}/ignore`, {});
  } catch (error) {
    back(slug, "erro", msg(error, "Falha."));
  }
  back(slug, "ok", "Atualizado.");
}
