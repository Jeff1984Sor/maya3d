"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { AdminApiError, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";

const text = (f: FormData, k: string) => String(f.get(k) ?? "").trim();
const optional = (f: FormData, k: string) => text(f, k) || null;
const list = (f: FormData, k: string) =>
  text(f, k)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

function fail(path: string, error: unknown): never {
  const msg = error instanceof AdminApiError ? error.message : "Falha ao falar com a API.";
  redirect(`${path}?erro=${encodeURIComponent(msg)}`);
}

function productFields(f: FormData) {
  return {
    niche: text(f, "niche"),
    category: text(f, "category"),
    subcategory: optional(f, "subcategory"),
    title: text(f, "title"),
    description: optional(f, "description"),
    tags: list(f, "tags"),
    occasions: list(f, "occasions"),
    min_material: optional(f, "min_material"),
    customizable: f.get("customizable") === "on",
  };
}

function designFields(f: FormData) {
  return {
    name: text(f, "design_name") || text(f, "title"),
    origin: text(f, "origin") || "parametrico",
    license: text(f, "license") || "próprio",
    author: optional(f, "author"),
    source_url: optional(f, "source_url"),
    attribution_text: optional(f, "attribution_text"),
  };
}

export async function createProduct(form: FormData): Promise<void> {
  await requireSession();
  let id: number;
  try {
    ({ id } = await api.post<{ id: number }>("/products", { ...productFields(form), design: designFields(form) }));
  } catch (error) {
    fail("/produtos/novo", error);
  }
  revalidatePath("/produtos");
  redirect(`/produtos/${id}?ok=${encodeURIComponent("Produto criado e verificado pelo Guardião.")}`);
}

export async function updateProduct(id: number, form: FormData): Promise<void> {
  await requireSession();
  try {
    await api.patch(`/products/${id}`, { ...productFields(form), design: designFields(form) });
  } catch (error) {
    fail(`/produtos/${id}`, error);
  }
  revalidatePath(`/produtos/${id}`);
  redirect(`/produtos/${id}?ok=${encodeURIComponent("Salvo. O Guardião verificou de novo.")}`);
}

export async function setStatus(id: number, status: "rascunho" | "ativo" | "pausado"): Promise<void> {
  await requireSession();
  try {
    await api.patch(`/products/${id}`, { status });
  } catch (error) {
    fail(`/produtos/${id}`, error);
  }
  revalidatePath("/produtos");
  redirect(`/produtos/${id}?ok=${encodeURIComponent(`Status: ${status}.`)}`);
}

export async function deleteProduct(id: number): Promise<void> {
  await requireSession();
  try {
    await api.delete(`/products/${id}`);
  } catch (error) {
    fail(`/produtos/${id}`, error);
  }
  revalidatePath("/produtos");
  redirect(`/produtos?ok=${encodeURIComponent("Produto removido.")}`);
}

function variantFields(f: FormData) {
  const grams: Record<string, number> = {};
  for (const i of [1, 2, 3]) {
    const material = text(f, `material_${i}`);
    const g = Number(text(f, `grams_${i}`).replace(",", "."));
    if (material && g > 0) grams[material] = g;
  }
  const hours = Number(text(f, "print_hours").replace(",", "."));
  const packaging = text(f, "packaging_id");
  const weight = Number(text(f, "packed_weight_g"));
  return {
    size_label: optional(f, "size_label"),
    finish: text(f, "finish") || "cor_unica",
    grams_by_material: Object.keys(grams).length ? grams : null,
    print_seconds: hours > 0 ? Math.round(hours * 3600) : null,
    post_minutes: Number(text(f, "post_minutes") || 0),
    packaging_id: packaging ? Number(packaging) : null,
    packed_weight_g: weight > 0 ? weight : null,
  };
}

export async function addVariant(productId: number, form: FormData): Promise<void> {
  await requireSession();
  try {
    await api.post(`/products/${productId}/variants`, { ...variantFields(form), sku: optional(form, "sku") });
  } catch (error) {
    fail(`/produtos/${productId}`, error);
  }
  revalidatePath(`/produtos/${productId}`);
  redirect(`/produtos/${productId}?ok=${encodeURIComponent("Variante adicionada.")}`);
}

export async function deleteVariant(productId: number, variantId: number): Promise<void> {
  await requireSession();
  try {
    await api.delete(`/products/${productId}/variants/${variantId}`);
  } catch (error) {
    fail(`/produtos/${productId}`, error);
  }
  revalidatePath(`/produtos/${productId}`);
  redirect(`/produtos/${productId}?ok=${encodeURIComponent("Variante removida.")}`);
}
