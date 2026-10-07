import type { ProductSummary } from "@/lib/types";
import { Badge } from "./ui";

export function GuardianBadge({ status }: { status: ProductSummary["guardian_status"] }) {
  if (status === "aprovado") return <Badge tone="ok">Guardião: aprovado</Badge>;
  if (status === "bloqueado") return <Badge tone="danger">Guardião: bloqueado</Badge>;
  return <Badge>Guardião: pendente</Badge>;
}

export function StatusBadge({ product }: { product: Pick<ProductSummary, "status" | "available"> }) {
  if (!product.available) return <Badge tone="warn">aguardando equipamento</Badge>;
  if (product.status === "ativo") return <Badge tone="ok">ativo</Badge>;
  if (product.status === "pausado") return <Badge tone="warn">pausado</Badge>;
  return <Badge>rascunho</Badge>;
}
