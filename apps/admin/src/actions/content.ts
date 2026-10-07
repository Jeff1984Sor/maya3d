"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { AdminApiError, adminApi, api } from "@/lib/admin-api";
import { requireSession } from "@/lib/auth";
import { SOCIALS, TOKENS } from "@/lib/content";

export type Brand = {
  name: string;
  tagline: string | null;
  colors: { light: Record<string, string>; dark: Record<string, string> };
  contact_email: string | null;
  contact_whatsapp: string | null;
  social: Record<string, string>;
  cnpj: string | null;
  legal_name: string | null;
  voice: string | null;
  logo_light_url: string | null;
  logo_dark_url: string | null;
  favicon_url: string | null;
};
export type Section = { title: string; kind: string; value: string; limit: number };
export type Layout = {
  announcement: string | null;
  hero: { title?: string | null; subtitle?: string | null; image_key?: string | null; cta_label?: string | null; cta_href?: string | null };
  sections: Section[];
};
export type Page = { slug: string; title: string; body: string; published: boolean; in_footer: boolean; position: number };
export type VisualFinding = { kind: string; description: string; confidence: number };
export type ProductImage = {
  id: number;
  key: string;
  thumb_key: string;
  alt: string | null;
  position: number;
  visual_status: "pendente" | "ok" | "alerta" | "bloqueado" | "liberado" | "erro";
  visual_notes: { summary?: string; findings?: VisualFinding[]; released_reason?: string };
};


const msg = (e: unknown, f: string) => (e instanceof AdminApiError ? e.message : f);
const t = (f: FormData, k: string) => String(f.get(k) ?? "").trim();
const go = (path: string, key: "ok" | "erro", m: string): never => redirect(`${path}${path.includes("?") ? "&" : "?"}${key}=${encodeURIComponent(m)}`);

/** Envio de arquivo (multipart) para a API, a partir de uma server action. */
async function upload<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  return adminApi<T>(path, { method: "POST", body });
}

// --- Marca ----------------------------------------------------------------------------------
export async function saveBrand(form: FormData): Promise<void> {
  await requireSession();
  const colors = { light: {} as Record<string, string>, dark: {} as Record<string, string> };
  for (const mode of ["light", "dark"] as const)
    for (const token of TOKENS) {
      const v = t(form, `${mode}_${token}`);
      if (v) colors[mode][token] = v.toUpperCase();
    }
  const social: Record<string, string> = {};
  for (const s of SOCIALS) if (t(form, `social_${s}`)) social[s] = t(form, `social_${s}`);
  try {
    await api.put("/brand", {
      name: t(form, "name"),
      tagline: t(form, "tagline") || null,
      colors,
      contact_email: t(form, "contact_email") || null,
      contact_whatsapp: t(form, "contact_whatsapp") || null,
      social,
      cnpj: t(form, "cnpj") || null,
      legal_name: t(form, "legal_name") || null,
      voice: t(form, "voice") || null,
    });
  } catch (e) {
    go("/marca", "erro", msg(e, "Falha ao salvar."));
  }
  revalidatePath("/", "layout");
  go("/marca", "ok", "Marca salva. A loja atualiza em até 1 minuto.");
}

export async function uploadLogo(kind: "light" | "dark" | "favicon", form: FormData): Promise<void> {
  await requireSession();
  const file = form.get("file");
  if (!(file instanceof File) || !file.size) go("/marca", "erro", "Escolha uma imagem.");
  try {
    await upload(`/brand/logo/${kind}`, file as File);
  } catch (e) {
    go("/marca", "erro", msg(e, "Falha ao enviar."));
  }
  go("/marca", "ok", "Imagem atualizada.");
}

// --- Página inicial -------------------------------------------------------------------------
export async function saveLayout(form: FormData): Promise<void> {
  await requireSession();
  const sections: Section[] = [];
  for (let i = 0; i < 6; i++) {
    const title = t(form, `s${i}_title`);
    if (!title) continue;
    sections.push({ title, kind: t(form, `s${i}_kind`) || "newest", value: t(form, `s${i}_value`), limit: Number(t(form, `s${i}_limit`) || 8) });
  }
  try {
    await api.put("/store-layout", {
      announcement: t(form, "announcement") || null,
      hero: {
        title: t(form, "hero_title") || null,
        subtitle: t(form, "hero_subtitle") || null,
        image_key: t(form, "hero_image_key") || null,
        cta_label: t(form, "hero_cta_label") || null,
        cta_href: t(form, "hero_cta_href") || null,
      },
      sections,
    });
  } catch (e) {
    go("/loja", "erro", msg(e, "Falha ao salvar."));
  }
  go("/loja", "ok", "Página inicial salva. A loja atualiza em até 1 minuto.");
}

export async function uploadHeroImage(form: FormData): Promise<void> {
  await requireSession();
  const file = form.get("file");
  if (!(file instanceof File) || !file.size) go("/loja", "erro", "Escolha uma imagem.");
  try {
    await upload("/store-layout/hero-image", file as File);
  } catch (e) {
    go("/loja", "erro", msg(e, "Falha ao enviar."));
  }
  go("/loja", "ok", "Imagem do destaque atualizada.");
}

// --- Páginas --------------------------------------------------------------------------------
export async function savePage(slug: string | null, form: FormData): Promise<void> {
  await requireSession();
  const target = slug ?? t(form, "slug");
  try {
    await api.put(`/pages/${encodeURIComponent(target)}`, {
      title: t(form, "title"),
      body: String(form.get("body") ?? ""),
      published: form.get("published") === "on",
      in_footer: form.get("in_footer") === "on",
      position: Number(t(form, "position") || 0),
    });
  } catch (e) {
    go(slug ? `/paginas/${slug}` : "/paginas", "erro", msg(e, "Falha ao salvar."));
  }
  revalidatePath("/paginas");
  go(`/paginas/${target}`, "ok", "Página salva.");
}

export async function deletePage(slug: string): Promise<void> {
  await requireSession();
  try {
    await api.delete(`/pages/${encodeURIComponent(slug)}`);
  } catch (e) {
    go(`/paginas/${slug}`, "erro", msg(e, "Falha ao remover."));
  }
  revalidatePath("/paginas");
  go("/paginas", "ok", "Página removida.");
}

// --- Fotos do produto ----------------------------------------------------------------------
export async function uploadProductImages(productId: number, form: FormData): Promise<void> {
  await requireSession();
  const back = `/produtos/${productId}`;
  const files = form.getAll("files").filter((f): f is File => f instanceof File && f.size > 0);
  if (!files.length) go(back, "erro", "Escolha uma ou mais fotos.");
  let sent = 0;
  for (const file of files) {
    try {
      await upload(`/products/${productId}/images`, file);
      sent++;
    } catch (e) {
      go(back, "erro", `${sent} enviada(s); ${file.name}: ${msg(e, "falhou")}`);
    }
  }
  revalidatePath(back);
  go(back, "ok", `${sent} foto(s) enviada(s).`);
}

export async function imageAction(productId: number, imageId: number, action: "cover" | "delete"): Promise<void> {
  await requireSession();
  const back = `/produtos/${productId}`;
  try {
    if (action === "delete") await api.delete(`/products/${productId}/images/${imageId}`);
    else await api.post(`/products/${productId}/images/${imageId}/cover`, {});
  } catch (e) {
    go(back, "erro", msg(e, "Falha."));
  }
  revalidatePath(back);
  go(back, "ok", action === "delete" ? "Foto removida." : "Capa definida.");
}

// --- Guardião visual ------------------------------------------------------------------------
export async function runVisualCheck(productId: number): Promise<void> {
  await requireSession();
  const back = `/produtos/${productId}`;
  try {
    await api.post(`/products/${productId}/images/visual-check`, {});
  } catch (e) {
    go(back, "erro", msg(e, "Falha ao verificar as fotos."));
  }
  revalidatePath(back);
  go(back, "ok", "Fotos verificadas pelo Guardião visual.");
}

export async function releaseImage(productId: number, imageId: number, form: FormData): Promise<void> {
  await requireSession();
  const back = `/produtos/${productId}`;
  try {
    await api.post(`/products/${productId}/images/${imageId}/release`, { reason: t(form, "reason") });
  } catch (e) {
    go(back, "erro", msg(e, "Explique o motivo (mín. 5 letras)."));
  }
  revalidatePath(back);
  go(back, "ok", "Foto liberada. Ficou registrado na auditoria.");
}
