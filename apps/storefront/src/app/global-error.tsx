"use client";

import "./globals.css";

/** Último recurso: erro no navegador fora de uma página (ex.: no cabeçalho ou no assistente). */
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="pt-BR">
      <body className="grid min-h-dvh place-items-center px-6 text-center">
        <div className="max-w-md space-y-4">
          <h1 className="text-3xl">Algo deu errado por aqui</h1>
          <p className="text-muted">Pode ter sido a conexão ou uma atualização da loja. Recarregue para continuar de onde parou.</p>
          <button type="button" onClick={() => (window.location.reload(), reset())} className="btn">
            Recarregar
          </button>
        </div>
      </body>
    </html>
  );
}
