import Link from "next/link";
import { requireSession } from "@/lib/auth";
import { RESOURCES } from "@/lib/resources";
import { signOut } from "../login/actions";

const TOOLS = [
  { href: "/", label: "Visão geral" },
  { href: "/producao", label: "Produção" },
  { href: "/pedidos", label: "Pedidos" },
  { href: "/fila", label: "Fila de impressão" },
  { href: "/produtos", label: "Produtos" },
  { href: "/parametricos", label: "Paramétricos" },
  { href: "/dividir", label: "Dividir peça grande" },
  { href: "/calculadora", label: "Calculadora de preço" },
  { href: "/comparativo", label: "Comparativo de materiais" },
  { href: "/guardiao", label: "Guardião" },
  { href: "/auditoria", label: "Auditoria" },
  { href: "/custos", label: "Custos" },
  { href: "/operacao", label: "Operação" },
  { href: "/ia", label: "IA" },
  { href: "/mensagens", label: "Caixa de saída" },
];

export default async function PainelLayout({ children }: { children: React.ReactNode }) {
  await requireSession();
  return (
    <div className="min-h-dvh md:flex">
      <aside className="border-b border-border bg-surface md:min-h-dvh md:w-60 md:shrink-0 md:border-b-0 md:border-r">
        <nav className="flex gap-1 overflow-x-auto p-3 text-sm md:flex-col md:p-4">
          <p className="hidden px-3 pb-1 pt-2 text-xs font-medium uppercase tracking-widest text-muted md:block">Ferramentas</p>
          {TOOLS.map((l) => (
            <Link key={l.href} href={l.href} className="whitespace-nowrap rounded-lg px-3 py-2 hover:bg-bg">
              {l.label}
            </Link>
          ))}
          <p className="hidden px-3 pb-1 pt-4 text-xs font-medium uppercase tracking-widest text-muted md:block">Cadastros</p>
          {RESOURCES.map((r) => (
            <Link key={r.slug} href={`/${r.slug}`} className="whitespace-nowrap rounded-lg px-3 py-2 hover:bg-bg">
              {r.title}
            </Link>
          ))}
          <form action={signOut} className="md:mt-6">
            <button type="submit" className="whitespace-nowrap rounded-lg px-3 py-2 text-muted hover:bg-bg">
              Sair
            </button>
          </form>
        </nav>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-8 md:px-10">{children}</main>
    </div>
  );
}
