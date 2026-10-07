"use client";

import { useState } from "react";

export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="rounded-lg bg-secondary px-3 py-2 text-sm font-medium text-white"
    >
      {copied ? "Copiado!" : "Copiar chave"}
    </button>
  );
}
