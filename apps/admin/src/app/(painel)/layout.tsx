import { requireSession } from "@/lib/auth";
import { RESOURCES } from "@/lib/resources";
import { SideNav, type NavGroup } from "@/components/side-nav";
import { signOut } from "../login/actions";

// cadastro gerado de resources.ts → grupo do menu (o que não estiver aqui cai em Cadastros)
const RESOURCE_GROUP: Record<string, string> = {
  clientes: "Vendas",
  materiais: "Produção",
  impressoras: "Produção",
  embalagens: "Produção",
  tarifas: "Preços e custos",
  nichos: "Catálogo",
  licencas: "Catálogo",
  termos: "Catálogo",
};

const GROUPS: NavGroup[] = [
  {
    title: "Início",
    icon: "🏠",
    items: [
      { href: "/", label: "Visão geral" },
      { href: "/assistente", label: "🤖 Assistente" },
    ],
  },
  {
    title: "Vendas",
    icon: "🛒",
    items: [
      { href: "/pedidos", label: "Pedidos" },
      { href: "/mercado-livre", label: "Mercado Livre" },
      { href: "/shopee", label: "Shopee" },
      { href: "/mensagens", label: "Caixa de saída (WhatsApp)" },
    ],
  },
  {
    title: "Produção",
    icon: "🖨️",
    items: [
      { href: "/producao", label: "Produção" },
      { href: "/fila", label: "Fila de impressão" },
    ],
  },
  {
    title: "Catálogo",
    icon: "📦",
    items: [
      { href: "/produtos", label: "Produtos" },
      { href: "/biblioteca", label: "Biblioteca de modelos" },
      { href: "/guardiao", label: "Guardião" },
    ],
  },
  {
    title: "Criar peças",
    icon: "✨",
    items: [
      { href: "/parametricos", label: "Paramétricos (placa, chaveiro…)" },
      { href: "/foto", label: "Foto vira peça" },
      { href: "/dividir", label: "Dividir peça grande" },
    ],
  },
  {
    title: "Preços e custos",
    icon: "💰",
    items: [
      { href: "/calculadora", label: "Calculadora de preço" },
      { href: "/comparativo", label: "Comparativo de materiais" },
      { href: "/custos", label: "Custos" },
    ],
  },
  {
    title: "Loja online",
    icon: "🏪",
    items: [
      { href: "/loja", label: "Página inicial da loja" },
      { href: "/paginas", label: "Páginas da loja" },
      { href: "/marca", label: "Marca" },
    ],
  },
  { title: "Cadastros", icon: "🗂️", items: [] },
  {
    title: "Configurações",
    icon: "⚙️",
    items: [
      { href: "/integracoes", label: "Integrações" },
      { href: "/ia", label: "IA" },
      { href: "/operacao", label: "Operação" },
      { href: "/auditoria", label: "Auditoria" },
    ],
  },
];

function menu(): NavGroup[] {
  const groups = GROUPS.map((g) => ({ ...g, items: [...g.items] }));
  for (const r of RESOURCES) {
    const target = groups.find((g) => g.title === (RESOURCE_GROUP[r.slug] ?? "Cadastros"))!;
    target.items.push({ href: `/${r.slug}`, label: r.title });
  }
  return groups.filter((g) => g.items.length > 0);
}

export default async function PainelLayout({ children }: { children: React.ReactNode }) {
  await requireSession();
  return (
    <div className="min-h-dvh md:flex">
      <SideNav
        groups={menu()}
        footer={
          <form action={signOut}>
            <button type="submit" className="w-full rounded-lg px-3 py-2 text-left text-muted hover:bg-bg">
              ↩ Sair
            </button>
          </form>
        }
      />
      <main className="min-w-0 flex-1 px-4 py-8 md:px-10">{children}</main>
    </div>
  );
}
