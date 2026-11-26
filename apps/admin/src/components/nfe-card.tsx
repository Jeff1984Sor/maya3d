import Link from "next/link";
import { cancelNfe, consultNfe, emitNfe, resendNfe } from "@/actions/fiscal";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { Badge, Button, Card, Label, inputClass } from "@/components/ui";
import { AdminApiError, api } from "@/lib/admin-api";
import { formatMoney } from "@/lib/form";

type Recipient = {
  nome: string;
  documento: string;
  email: string | null;
  ie: string | null;
  cep: string;
  logradouro: string;
  numero: string;
  complemento: string | null;
  bairro: string;
  municipio: string;
  uf: string;
  cod_municipio: string;
};

type Invoice = {
  id: number;
  ambiente: number;
  serie: number;
  number: number;
  status: string;
  chave: string | null;
  cstat: string | null;
  motivo: string | null;
  total: string;
  authorized_at: string | null;
  ml_status: string | null;
  email_status: string | null;
};

type OrderNfe = { invoices: Invoice[]; prefill: { recipient: Recipient; missing: string[]; note: string | null } };

const TONE: Record<string, "ok" | "danger" | "warn" | "muted"> = {
  autorizada: "ok",
  cancelada: "muted",
  rejeitada: "danger",
  denegada: "danger",
  sem_resposta: "warn",
  processando: "warn",
};

const FIELDS: { key: keyof Recipient; label: string; wide?: boolean }[] = [
  { key: "nome", label: "Nome / razão social", wide: true },
  { key: "documento", label: "CPF ou CNPJ" },
  { key: "email", label: "E-mail (opcional)" },
  { key: "cep", label: "CEP" },
  { key: "logradouro", label: "Rua", wide: true },
  { key: "numero", label: "Número" },
  { key: "complemento", label: "Complemento" },
  { key: "bairro", label: "Bairro" },
  { key: "municipio", label: "Cidade" },
  { key: "uf", label: "UF" },
  { key: "ie", label: "IE (só empresa contribuinte)" },
];

export async function NfeCard({ orderId, orderStatus }: { orderId: number; orderStatus: string }) {
  let data: OrderNfe;
  try {
    data = await api.get<OrderNfe>(`/orders/${orderId}/nfe`);
  } catch (error) {
    const msg = error instanceof AdminApiError ? error.message : "indisponível";
    return (
      <Card title="Nota fiscal">
        <p className="text-sm text-muted">{msg}</p>
      </Card>
    );
  }
  const back = `/pedidos/${orderId}`;
  const done = data.invoices.find((i) => i.status === "autorizada");
  const pending = data.invoices.find((i) => i.status === "sem_resposta" || i.status === "processando");
  const canEmit = !done && !pending && orderStatus !== "aguardando_pagamento" && orderStatus !== "cancelado";
  const r = data.prefill.recipient;

  return (
    <Card title="Nota fiscal">
      {data.invoices.length > 0 && (
        <ul className="mb-4 space-y-3 text-sm">
          {data.invoices.map((i) => (
            <li key={i.id} className="rounded-xl border border-border p-3">
              <p className="flex flex-wrap items-center gap-2">
                <span className="font-medium">
                  NF-e nº {i.number} · série {i.serie}
                </span>
                <Badge tone={TONE[i.status] ?? "muted"}>{i.status.replace("_", " ")}</Badge>
                {i.ambiente === 2 && <Badge tone="warn">teste</Badge>}
                <span className="text-muted">{formatMoney(Number(i.total))}</span>
              </p>
              {i.motivo && (
                <p className="mt-1 text-xs text-muted">
                  {i.cstat} {i.motivo}
                </p>
              )}
              {i.ml_status && <p className="mt-1 text-xs">Mercado Livre: {i.ml_status}</p>}
              {i.email_status && <p className="mt-1 text-xs">E-mail: {i.email_status}</p>}
              <div className="mt-2 flex flex-wrap gap-2">
                {(i.status === "autorizada" || i.status === "cancelada") && (
                  <>
                    <a
                      href={`/api/nfe/${i.id}/danfe`}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-lg border border-border px-2 py-1 text-xs text-secondary hover:underline"
                    >
                      🖨 DANFE (PDF)
                    </a>
                    <a href={`/api/nfe/${i.id}/xml`} className="rounded-lg border border-border px-2 py-1 text-xs text-secondary hover:underline">
                      ⬇ XML
                    </a>
                  </>
                )}
                {(i.status === "sem_resposta" || i.status === "processando") && (
                  <form action={consultNfe.bind(null, i.id, back)}>
                    <Button variant="secondary" className="px-2 py-1 text-xs">
                      Consultar na SEFAZ
                    </Button>
                  </form>
                )}
                {i.status === "autorizada" && (
                  <form action={resendNfe.bind(null, i.id, back)}>
                    <Button variant="secondary" className="px-2 py-1 text-xs">
                      Reenviar ao ML e por e-mail
                    </Button>
                  </form>
                )}
              </div>
              {i.status === "autorizada" && (
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer text-muted">cancelar esta nota (até 24 h)</summary>
                  <form action={cancelNfe.bind(null, i.id, back)} className="mt-2 space-y-2">
                    <input name="justificativa" minLength={15} maxLength={255} required placeholder="motivo (mínimo 15 letras)" className={inputClass} />
                    <ConfirmSubmit message="Cancelar a nota na SEFAZ? Não dá para desfazer." className="text-primary hover:underline">
                      Cancelar na SEFAZ
                    </ConfirmSubmit>
                  </form>
                </details>
              )}
            </li>
          ))}
        </ul>
      )}

      {canEmit ? (
        <form action={emitNfe.bind(null, orderId)} className="space-y-3">
          <p className="text-xs text-muted">
            Confira o destinatário{data.prefill.note ? ` (${data.prefill.note})` : ""}. Itens, valores, CFOP e NCM vêm do pedido e de{" "}
            <Link href="/nota-fiscal" className="text-secondary hover:underline">
              Nota fiscal
            </Link>
            .
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {FIELDS.map((f) => (
              <div key={f.key} className={f.wide ? "sm:col-span-2" : undefined}>
                <Label label={f.label}>
                  <input name={f.key} defaultValue={r[f.key] ?? ""} className={inputClass} />
                </Label>
              </div>
            ))}
          </div>
          {data.prefill.missing.length > 0 && <p className="text-xs text-primary">Falta: {data.prefill.missing.join(", ")}</p>}
          <Button type="submit">{data.invoices.some((i) => i.status === "rejeitada") ? "Corrigir e emitir de novo" : "Emitir NF-e"}</Button>
        </form>
      ) : (
        !done &&
        !pending && <p className="text-sm text-muted">A nota só pode ser emitida para pedido pago e não cancelado.</p>
      )}
    </Card>
  );
}
