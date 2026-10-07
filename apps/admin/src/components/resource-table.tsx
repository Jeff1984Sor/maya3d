import Link from "next/link";
import { deleteItem } from "@/actions/resources";
import { formatMoney, formatPercent } from "@/lib/form";
import type { Column, Resource } from "@/lib/resources";
import { ConfirmSubmit } from "./confirm-submit";
import { Badge, Empty } from "./ui";

type Row = Record<string, unknown> & { id: number };

function CellValue({ column, row }: { column: Column; row: Row }) {
  const value = row[column.name];
  switch (column.cell) {
    case "money":
      return <>{formatMoney(value)}</>;
    case "percent":
      return <>{formatPercent(value)}</>;
    case "color":
      return <span className="inline-block size-5 rounded-full border border-border" style={{ background: String(value) }} />;
    case "bool":
      return value ? <Badge tone="ok">sim</Badge> : <Badge>não</Badge>;
    case "list":
      return <>{Array.isArray(value) && value.length ? value.join(", ") : "—"}</>;
    case "lowStock":
      return value ? <Badge tone="warn">repor</Badge> : null;
    default:
      return <>{value === null || value === undefined || value === "" ? "—" : String(value)}</>;
  }
}

export function ResourceTable({ resource, rows }: { resource: Resource; rows: Row[] }) {
  if (rows.length === 0) return <Empty>Nenhum(a) {resource.singular} cadastrado(a) ainda.</Empty>;
  return (
    <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
          <tr>
            {resource.columns.map((c) => (
              <th key={c.name} className="px-4 py-3 font-medium">
                {c.label}
              </th>
            ))}
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-border last:border-0 hover:bg-bg/60">
              {resource.columns.map((c) => (
                <td key={c.name} className="px-4 py-3">
                  <CellValue column={c} row={row} />
                </td>
              ))}
              <td className="whitespace-nowrap px-4 py-3 text-right">
                <Link href={`/${resource.slug}/${row.id}`} className="mr-3 text-secondary hover:underline">
                  editar
                </Link>
                <form action={deleteItem.bind(null, resource.slug, row.id)} className="inline">
                  <ConfirmSubmit
                    message={`Remover este(a) ${resource.singular}? Não dá para desfazer.`}
                    className="text-primary hover:underline"
                  >
                    remover
                  </ConfirmSubmit>
                </form>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
