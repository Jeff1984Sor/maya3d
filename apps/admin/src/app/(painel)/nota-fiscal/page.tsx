import type { Metadata } from "next";
import Link from "next/link";
import { testSefaz, uploadCertificate } from "@/actions/fiscal";
import { Flash } from "@/components/flash";
import { Badge, Button, Card, Label, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/admin-api";

export const metadata: Metadata = { title: "Nota fiscal" };
export const dynamic = "force-dynamic";

type FiscalStatus = {
  ready: boolean;
  missing: string[];
  ambiente: "producao" | "homologacao";
  serie: number;
  next_number: number;
  certificate: { titular: string; cnpj: string | null; valido_ate: string; vencido: boolean } | null;
  certificate_error: string | null;
  email_ready: boolean;
};

export default async function NotaFiscalPage({ searchParams }: { searchParams: Promise<{ ok?: string; erro?: string }> }) {
  const st = await api.get<FiscalStatus>("/fiscal/status");
  const cert = st.certificate;
  return (
    <>
      <PageHeader
        title="Nota fiscal"
        description="NF-e emitida pela própria plataforma, direto na SEFAZ-SP, com o seu certificado A1. Emita em cada pedido (Pedidos → abrir o pedido → Nota fiscal)."
      />
      <Flash {...await searchParams} />
      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Situação">
          <ul className="space-y-2 text-sm">
            <li>
              <Badge tone={st.ready ? "ok" : "warn"}>{st.ready ? "pronto para emitir" : "falta configurar"}</Badge>
            </li>
            <li>
              Ambiente:{" "}
              <Badge tone={st.ambiente === "producao" ? "ok" : "warn"}>
                {st.ambiente === "producao" ? "produção (nota de verdade)" : "homologação (teste, sem valor fiscal)"}
              </Badge>
            </li>
            <li>
              Próxima nota: nº {st.next_number}, série {st.serie}
            </li>
            <li>
              E-mail com nota e etiqueta: <Badge tone={st.email_ready ? "ok" : "muted"}>{st.email_ready ? "configurado" : "não configurado"}</Badge>
            </li>
          </ul>
          {st.missing.length > 0 && <p className="mt-3 text-sm text-muted">Falta: {st.missing.join(", ")}.</p>}
          <div className="mt-4 flex flex-wrap gap-3 text-sm">
            <Link href="/integracoes#notafiscal" className="text-secondary hover:underline">
              dados da empresa, CFOP, NCM e e-mail em Integrações →
            </Link>
          </div>
          <form action={testSefaz} className="mt-4">
            <Button variant="secondary" disabled={!cert}>
              Testar conexão com a SEFAZ
            </Button>
          </form>
        </Card>

        <Card title="Certificado digital A1">
          {cert ? (
            <div className="mb-4 space-y-1 text-sm">
              <p>{cert.titular}</p>
              <p className="text-muted">CNPJ {cert.cnpj ?? "não encontrado"}</p>
              <p>
                Válido até {new Date(cert.valido_ate).toLocaleDateString("pt-BR")}{" "}
                {cert.vencido && <Badge tone="danger">vencido</Badge>}
              </p>
            </div>
          ) : (
            <p className="mb-4 text-sm text-muted">{st.certificate_error ?? "Nenhum certificado enviado ainda."}</p>
          )}
          <form action={uploadCertificate} className="space-y-4">
            <Label label="Arquivo do certificado" hint=".pfx ou .p12 (o mesmo que você instalou no emissor do Sebrae)">
              <input type="file" name="file" accept=".pfx,.p12" required className={inputClass} />
            </Label>
            <Label label="Senha do certificado" hint="fica cifrada no banco; ninguém vê depois, nem você">
              <input type="password" name="senha" required autoComplete="off" className={inputClass} />
            </Label>
            <Button type="submit">{cert ? "Trocar certificado" : "Enviar certificado"}</Button>
          </form>
        </Card>
      </div>
    </>
  );
}
