"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";
import { formToPayload } from "@/lib/form";
import { findResource, type Resource } from "@/lib/resources";

function resourceOr404(slug: string): Resource {
  const resource = findResource(slug);
  if (!resource) throw new Error(`cadastro desconhecido: ${slug}`);
  return resource;
}

function messageOf(error: unknown): string {
  return error instanceof AdminApiError ? error.message : "Falha inesperada ao falar com a API.";
}

/** Redireciona com mensagem na URL: funciona sem JavaScript e sobrevive a recarregar. */
function back(path: string, key: "ok" | "erro", message: string): never {
  redirect(`${path}?${key}=${encodeURIComponent(message)}`);
}

export async function createItem(slug: string, form: FormData): Promise<void> {
  await requireSession();
  const resource = resourceOr404(slug);
  try {
    await api.post(resource.apiPath, formToPayload(resource.fields, form, "create"));
  } catch (error) {
    back(`/${slug}`, "erro", messageOf(error));
  }
  revalidatePath(`/${slug}`);
  back(`/${slug}`, "ok", `${resource.singular} cadastrado(a).`);
}

export async function updateItem(slug: string, id: number, form: FormData): Promise<void> {
  await requireSession();
  const resource = resourceOr404(slug);
  try {
    await api.patch(`${resource.apiPath}/${id}`, formToPayload(resource.fields, form, "update"));
  } catch (error) {
    back(`/${slug}/${id}`, "erro", messageOf(error));
  }
  revalidatePath(`/${slug}`);
  back(`/${slug}`, "ok", `${resource.singular} atualizado(a).`);
}

export async function deleteItem(slug: string, id: number): Promise<void> {
  await requireSession();
  const resource = resourceOr404(slug);
  try {
    await api.delete(`${resource.apiPath}/${id}`);
  } catch (error) {
    back(`/${slug}`, "erro", messageOf(error));
  }
  revalidatePath(`/${slug}`);
  back(`/${slug}`, "ok", `${resource.singular} removido(a).`);
}
