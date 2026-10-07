"use client";

import type { ReactNode } from "react";

/** Botão de envio que pede confirmação antes de ações destrutivas. */
export function ConfirmSubmit({ message, children, className }: { message: string; children: ReactNode; className?: string }) {
  return (
    <button
      type="submit"
      className={className}
      onClick={(event) => {
        if (!window.confirm(message)) event.preventDefault();
      }}
    >
      {children}
    </button>
  );
}
