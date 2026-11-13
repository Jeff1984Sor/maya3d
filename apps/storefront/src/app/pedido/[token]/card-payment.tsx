"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { payCard, type CardData } from "@/actions/checkout";
import { money } from "@/lib/format";

/** SDK oficial (github.com/mercadopago/sdk-js): o número do cartão fica só no Mercado Pago. */
const SDK_URL = "https://sdk.mercadopago.com/js/v2";
const CONTAINER = "cardPaymentBrick_container";

type BrickController = { unmount: () => void };
type MercadoPagoCtor = new (
  publicKey: string,
  options: { locale: string },
) => { bricks: () => { create: (kind: string, container: string, settings: unknown) => Promise<BrickController> } };

declare global {
  interface Window {
    MercadoPago?: MercadoPagoCtor;
  }
}

function loadSdk(): Promise<MercadoPagoCtor> {
  if (window.MercadoPago) return Promise.resolve(window.MercadoPago);
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${SDK_URL}"]`);
    const script = existing ?? document.createElement("script");
    script.addEventListener("load", () => (window.MercadoPago ? resolve(window.MercadoPago) : reject(new Error("sdk"))));
    script.addEventListener("error", () => reject(new Error("sdk")));
    if (!existing) {
      script.src = SDK_URL;
      script.async = true;
      document.head.appendChild(script);
    }
  });
}

export function CardPayment({
  orderToken,
  publicKey,
  amount,
  email,
}: {
  orderToken: string;
  publicKey: string;
  amount: string;
  email: string | null;
}) {
  const router = useRouter();
  const [message, setMessage] = useState<{ tone: "ok" | "erro" | "info"; text: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const controller = useRef<BrickController | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadSdk()
      .then(async (MercadoPago) => {
        if (cancelled) return;
        const mp = new MercadoPago(publicKey, { locale: "pt-BR" });
        controller.current = await mp.bricks().create("cardPayment", CONTAINER, {
          initialization: { amount: Number(amount), payer: email ? { email } : undefined },
          customization: { paymentMethods: { maxInstallments: 12 } },
          callbacks: {
            onReady: () => setLoading(false),
            onError: () => setMessage({ tone: "erro", text: "Confira os dados do cartão e tente de novo." }),
            onSubmit: async (data: CardData) => {
              setMessage(null);
              const res = await payCard(orderToken, data).catch(() => ({ error: "Falha de conexão: tente de novo." }));
              if ("error" in res) {
                setMessage({ tone: "erro", text: res.error });
                return;
              }
              setMessage({ tone: res.paid ? "ok" : res.status === "rejected" ? "erro" : "info", text: res.message });
              if (res.paid || res.status !== "rejected") router.refresh();
            },
          },
        });
      })
      .catch(() => {
        setLoading(false);
        setMessage({ tone: "erro", text: "Não foi possível abrir o pagamento com cartão. Recarregue a página." });
      });
    return () => {
      cancelled = true;
      controller.current?.unmount();
      controller.current = null;
    };
  }, [orderToken, publicKey, amount, email, router]);

  return (
    <section className="mt-8 rounded-3xl border-2 border-secondary bg-secondary/5 p-6">
      <h2 className="text-xl">Pague com cartão</h2>
      <p className="mt-1 text-sm text-muted">
        Valor: <strong className="text-ink">{money(amount)}</strong> · em até 12x · dados do cartão protegidos pelo Mercado Pago
      </p>
      {message && (
        <p
          role="status"
          className={`mt-4 rounded-xl p-3 text-sm ${message.tone === "ok" ? "bg-secondary/15 text-ink" : message.tone === "erro" ? "bg-primary/10 text-primary" : "bg-soft text-ink"}`}
        >
          {message.text}
        </p>
      )}
      {loading && <p className="mt-4 text-sm text-muted">Carregando o pagamento seguro…</p>}
      <div id={CONTAINER} className="mt-4" />
    </section>
  );
}
