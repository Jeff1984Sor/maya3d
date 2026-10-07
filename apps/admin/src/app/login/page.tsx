import type { Metadata } from "next";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Entrar" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  // Só caminhos internos: evita redirecionamento aberto para outro site.
  const safeNext = next?.startsWith("/") && !next.startsWith("//") ? next : "/";
  return (
    <main className="flex min-h-dvh items-center justify-center px-6">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8">
        <p className="text-sm uppercase tracking-widest text-muted">Painel</p>
        <h1 className="mb-6 font-heading text-2xl font-bold">Entrar</h1>
        <LoginForm next={safeNext} />
      </div>
    </main>
  );
}
