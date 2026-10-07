import type { Metadata } from "next";
import { saveBrand, uploadLogo, type Brand } from "@/actions/content";
import { Flash } from "@/components/flash";
import { Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/admin-api";
import { SOCIALS, TOKEN_LABELS, TOKENS } from "@/lib/content";

export const metadata: Metadata = { title: "Marca" };
export const dynamic = "force-dynamic";

/** Caminho público (/m/media/...) → arquivo no proxy autenticado do painel. */
const preview = (url: string | null) => (url?.startsWith("/m/") ? `/api/files/${url.slice(3)}` : null);

export default async function MarcaPage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const brand = await api.get<Brand>("/brand");
  return (
    <>
      <PageHeader
        title="Marca"
        description="Nome, cores, logo e contatos da loja. Mudou o nome da loja? É só trocar aqui: nada no código depende dele."
      />
      <Flash {...await searchParams} />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <Card>
          <form action={saveBrand} className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <Label label="Nome da loja">
                <input name="name" required defaultValue={brand.name} className={inputClass} />
              </Label>
              <Label label="Frase (aparece no topo da loja)">
                <input name="tagline" defaultValue={brand.tagline ?? ""} className={inputClass} />
              </Label>
              <Label label="E-mail de contato">
                <input name="contact_email" type="email" defaultValue={brand.contact_email ?? ""} className={inputClass} />
              </Label>
              <Label label="WhatsApp da loja" hint="com DDD, ex.: +55 15 99999-0000">
                <input name="contact_whatsapp" defaultValue={brand.contact_whatsapp ?? ""} className={inputClass} />
              </Label>
              <Label label="Razão social">
                <input name="legal_name" defaultValue={brand.legal_name ?? ""} className={inputClass} />
              </Label>
              <Label label="CNPJ">
                <input name="cnpj" defaultValue={brand.cnpj ?? ""} className={inputClass} />
              </Label>
            </div>

            <div>
              <p className="mb-2 text-sm font-medium">Cores</p>
              <div className="overflow-x-auto">
                <table className="text-sm">
                  <thead>
                    <tr className="text-left text-xs text-muted">
                      <th className="pb-2 pr-4 font-normal">Uso</th>
                      <th className="pb-2 pr-4 font-normal">Tema claro</th>
                      <th className="pb-2 font-normal">Tema escuro</th>
                    </tr>
                  </thead>
                  <tbody>
                    {TOKENS.map((token) => (
                      <tr key={token}>
                        <td className="py-1 pr-4">{TOKEN_LABELS[token]}</td>
                        {(["light", "dark"] as const).map((mode) => (
                          <td key={mode} className="py-1 pr-4">
                            <input
                              type="color"
                              name={`${mode}_${token}`}
                              defaultValue={brand.colors[mode]?.[token] ?? "#000000"}
                              className="h-8 w-14 cursor-pointer rounded border border-border"
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {SOCIALS.map((s) => (
                <Label key={s} label={s[0]!.toUpperCase() + s.slice(1)}>
                  <input name={`social_${s}`} type="url" placeholder="https://" defaultValue={brand.social[s] ?? ""} className={inputClass} />
                </Label>
              ))}
            </div>

            <Label label="Voz da marca (para a IA)" hint="como a loja fala: ex. acolhedora, simples, sem gírias">
              <textarea name="voice" rows={3} defaultValue={brand.voice ?? ""} className={inputClass} />
            </Label>
            <Button type="submit">Salvar marca</Button>
          </form>
        </Card>

        <div className="space-y-6">
          {(
            [
              ["light", "Logo (fundo claro)", brand.logo_light_url],
              ["dark", "Logo (fundo escuro)", brand.logo_dark_url],
              ["favicon", "Ícone da aba (quadrado)", brand.favicon_url],
            ] as const
          ).map(([kind, label, url]) => (
            <Card key={kind} title={label}>
              {preview(url) && (
                // eslint-disable-next-line @next/next/no-img-element -- arquivo privado pelo proxy do painel
                <img src={preview(url)!} alt={label} className="mb-3 max-h-24 rounded border border-border bg-white p-2" />
              )}
              <form action={uploadLogo.bind(null, kind)} className="flex flex-col gap-2">
                <input type="file" name="file" accept="image/png,image/jpeg,image/webp" className="text-sm" />
                <Button variant="secondary">Enviar</Button>
              </form>
            </Card>
          ))}
        </div>
      </div>
    </>
  );
}
