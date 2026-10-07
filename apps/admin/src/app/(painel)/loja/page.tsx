import type { Metadata } from "next";
import { saveLayout, uploadHeroImage, type Layout } from "@/actions/content";
import { Flash } from "@/components/flash";
import { Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/admin-api";
import { SECTION_KINDS } from "@/lib/content";

export const metadata: Metadata = { title: "Página inicial" };
export const dynamic = "force-dynamic";

const SLOTS = 6;

export default async function LojaPage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const layout = await api.get<Layout>("/store-layout");
  const hero = layout.hero ?? {};
  const sections = [...layout.sections, ...Array(Math.max(0, SLOTS - layout.sections.length)).fill(null)].slice(0, SLOTS);
  return (
    <>
      <PageHeader title="Página inicial da loja" description="Aviso do topo, destaque principal e as vitrines de produtos, na ordem que você quiser." />
      <Flash {...await searchParams} />
      <form action={saveLayout} className="space-y-6">
        <Card title="Aviso no topo">
          <Label label="Texto" hint="vazio = aviso automático de frete grátis em Sorocaba">
            <input name="announcement" maxLength={200} defaultValue={layout.announcement ?? ""} className={inputClass} />
          </Label>
        </Card>

        <Card title="Destaque principal">
          <div className="grid gap-4 sm:grid-cols-2">
            <Label label="Título" hint="vazio = frase da marca">
              <input name="hero_title" maxLength={120} defaultValue={hero.title ?? ""} className={inputClass} />
            </Label>
            <Label label="Subtítulo">
              <input name="hero_subtitle" maxLength={240} defaultValue={hero.subtitle ?? ""} className={inputClass} />
            </Label>
            <Label label="Texto do botão">
              <input name="hero_cta_label" maxLength={40} defaultValue={hero.cta_label ?? ""} placeholder="Ver catálogo" className={inputClass} />
            </Label>
            <Label label="Botão leva para" hint="caminho da loja, ex.: /c/religioso">
              <input name="hero_cta_href" maxLength={200} defaultValue={hero.cta_href ?? ""} placeholder="/busca" className={inputClass} />
            </Label>
          </div>
          <input type="hidden" name="hero_image_key" defaultValue={hero.image_key ?? ""} />
          {hero.image_key && (
            // eslint-disable-next-line @next/next/no-img-element -- arquivo pelo proxy do painel
            <img src={`/api/files/${hero.image_key}`} alt="" className="mt-4 max-h-40 rounded-xl border border-border" />
          )}
        </Card>

        <Card title="Vitrines (na ordem)">
          <div className="space-y-3">
            {sections.map((s, i) => (
              <div key={i} className="grid gap-2 rounded-xl border border-border p-3 sm:grid-cols-[1fr_12rem_1fr_5rem]">
                <input name={`s${i}_title`} defaultValue={s?.title ?? ""} placeholder={`Vitrine ${i + 1} (vazio = não mostra)`} className={inputClass} />
                <select name={`s${i}_kind`} defaultValue={s?.kind ?? "newest"} className={inputClass}>
                  {SECTION_KINDS.map((k) => (
                    <option key={k.id} value={k.id}>
                      {k.label}
                    </option>
                  ))}
                </select>
                <input name={`s${i}_value`} defaultValue={s?.value ?? ""} placeholder="tema, categoria, tag ou produtos" className={inputClass} />
                <input name={`s${i}_limit`} type="number" min={1} max={24} defaultValue={s?.limit ?? 8} className={inputClass} aria-label="Quantidade" />
              </div>
            ))}
          </div>
          <ul className="mt-3 space-y-0.5 text-xs text-muted">
            {SECTION_KINDS.filter((k) => k.hint).map((k) => (
              <li key={k.id}>
                <b>{k.label}:</b> {k.hint}
              </li>
            ))}
          </ul>
        </Card>
        <Button type="submit">Salvar página inicial</Button>
      </form>

      <Card title="Imagem do destaque" className="mt-6">
        <form action={uploadHeroImage} className="flex flex-wrap items-center gap-3">
          <input type="file" name="file" accept="image/png,image/jpeg,image/webp" className="text-sm" />
          <Button variant="secondary">Enviar imagem</Button>
          <span className="text-xs text-muted">Foto horizontal, de preferência 1600 × 1200.</span>
        </form>
      </Card>
    </>
  );
}
