"use client";

import Link from "next/link";

/** Erro numa página da loja: mantém cabeçalho e rodapé, oferece tentar de novo. */
export default function PageError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-md space-y-4 px-6 py-20 text-center">
      <h1 className="text-3xl">Algo deu errado por aqui</h1>
      <p className="text-muted">Pode ter sido a conexão ou uma atualização da loja.</p>
      <div className="flex flex-wrap justify-center gap-3">
        <button type="button" onClick={() => reset()} className="btn">
          Tentar de novo
        </button>
        <Link href="/" className="btn-outline">
          Voltar ao início
        </Link>
      </div>
    </div>
  );
}
