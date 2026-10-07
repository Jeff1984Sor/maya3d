"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Atualiza a página do pedido enquanto o Pix não é confirmado. */
export function AutoRefresh({ seconds }: { seconds: number }) {
  const router = useRouter();
  useEffect(() => {
    const t = setInterval(() => router.refresh(), seconds * 1000);
    return () => clearInterval(t);
  }, [router, seconds]);
  return null;
}
