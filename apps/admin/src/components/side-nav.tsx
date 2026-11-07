"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

export type NavItem = { href: string; label: string };
export type NavGroup = { title: string; icon: string; items: NavItem[] };

function fold(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** Menu lateral em grupos: busca, página atual destacada e grupos que abrem e fecham. */
export function SideNav({ groups, footer }: { groups: NavGroup[]; footer: React.ReactNode }) {
  const pathname = usePathname();
  const [query, setQuery] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const activeGroup = groups.find((g) => g.items.some((i) => isActive(pathname, i.href)))?.title;
  const [open, setOpen] = useState<Set<string>>(() => new Set([activeGroup ?? groups[0]?.title ?? ""]));

  useEffect(() => {
    setMobileOpen(false);
    if (activeGroup) setOpen((prev) => (prev.has(activeGroup) ? prev : new Set(prev).add(activeGroup)));
  }, [pathname, activeGroup]);

  const q = fold(query.trim());
  const visible = groups
    .map((g) => ({ ...g, items: q ? g.items.filter((i) => fold(i.label).includes(q) || fold(g.title).includes(q)) : g.items }))
    .filter((g) => g.items.length > 0);

  function toggle(title: string) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      return next;
    });
  }

  return (
    <aside className="border-b border-border bg-surface md:sticky md:top-0 md:h-dvh md:w-64 md:shrink-0 md:border-b-0 md:border-r">
      <div className="flex items-center justify-between p-3 md:hidden">
        <span className="text-sm font-medium">Painel</span>
        <button
          type="button"
          onClick={() => setMobileOpen((v) => !v)}
          aria-expanded={mobileOpen}
          className="rounded-lg border border-border px-3 py-1.5 text-sm"
        >
          {mobileOpen ? "✕ Fechar" : "☰ Menu"}
        </button>
      </div>
      <nav className={`${mobileOpen ? "flex" : "hidden"} max-h-[80dvh] flex-col gap-1 overflow-y-auto p-3 text-sm md:flex md:h-full md:max-h-none md:p-4`}>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="🔎 Buscar no menu"
          className="mb-2 w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm outline-none focus:border-secondary"
        />
        {visible.map((g) => {
          const expanded = q.length > 0 || open.has(g.title);
          return (
            <div key={g.title} className="mb-1">
              <button
                type="button"
                onClick={() => toggle(g.title)}
                aria-expanded={expanded}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted hover:bg-bg"
              >
                <span className="text-base leading-none">{g.icon}</span>
                <span className="flex-1 text-left">{g.title}</span>
                <span className={`transition-transform ${expanded ? "rotate-90" : ""}`}>›</span>
              </button>
              {expanded && (
                <div className="ml-4 mt-0.5 flex flex-col border-l border-border pl-2">
                  {g.items.map((i) => {
                    const active = isActive(pathname, i.href);
                    return (
                      <Link
                        key={i.href}
                        href={i.href}
                        aria-current={active ? "page" : undefined}
                        className={`rounded-lg px-3 py-1.5 ${active ? "bg-secondary/15 font-medium text-secondary" : "hover:bg-bg"}`}
                      >
                        {i.label}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
        {visible.length === 0 && <p className="px-3 py-2 text-muted">Nada com “{query}”.</p>}
        <div className="mt-auto pt-4">{footer}</div>
      </nav>
    </aside>
  );
}
