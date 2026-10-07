"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useTransition } from "react";
import { askAssistant, type ChatTurn } from "@/actions/assistant";
import { money } from "@/lib/format";
import type { ProductCard } from "@/lib/store";

type Message = ChatTurn & { products?: ProductCard[] };

const STARTERS = ["Presente para madrinha de batismo", "Lembrancinha para aniversário", "Algo personalizado com nome"];

/** 🛍️ Assistente de compra: bolha no canto, conversa curta, indica peças do catálogo. */
export function Assistant({ brand }: { brand: string }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>(STARTERS);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [messages, pending]);

  function send(text: string) {
    const content = text.trim().slice(0, 600);
    if (!content || pending) return;
    const history: Message[] = [...messages, { role: "user", content }];
    setMessages(history);
    setInput("");
    setError(null);
    setSuggestions([]);
    start(async () => {
      const res = await askAssistant(history.map(({ role, content: c }) => ({ role, content: c })));
      if ("error" in res) {
        setError(res.error);
        return;
      }
      setMessages((m) => [...m, { role: "assistant", content: res.reply, products: res.products }]);
      setSuggestions(res.suggestions);
    });
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-3">
      {open && (
        <section
          aria-label="Assistente de compras"
          className="flex h-[min(34rem,calc(100dvh-6rem))] w-[min(24rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl"
        >
          <header className="flex items-center justify-between border-b border-border px-4 py-3">
            <div>
              <p className="font-heading font-semibold">Ajuda para escolher</p>
              <p className="text-xs text-muted">Assistente da {brand} · respostas por IA</p>
            </div>
            <button onClick={() => setOpen(false)} className="rounded-full px-2 text-muted hover:text-ink" aria-label="Fechar">
              ✕
            </button>
          </header>
          <div className="flex-1 space-y-3 overflow-y-auto p-4 text-sm">
            <p className="rounded-2xl rounded-tl-sm bg-bg px-3 py-2">
              Oi! Me conta para quem é ou qual a ocasião, que eu te mostro peças que combinam. 😊
            </p>
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
                <p
                  className={
                    m.role === "user"
                      ? "max-w-[85%] rounded-2xl rounded-tr-sm bg-primary px-3 py-2 text-white"
                      : "max-w-[90%] rounded-2xl rounded-tl-sm bg-bg px-3 py-2"
                  }
                >
                  {m.content}
                </p>
                {m.products && m.products.length > 0 && (
                  <div className="mt-2 grid gap-2">
                    {m.products.map((p) => (
                      <Link
                        key={p.slug}
                        href={`/p/${p.slug}`}
                        onClick={() => setOpen(false)}
                        className="flex items-center justify-between gap-3 rounded-xl border border-border px-3 py-2 hover:border-secondary"
                      >
                        <span className="line-clamp-2">{p.title}</span>
                        <span className="shrink-0 font-semibold text-primary">{p.price_from ? money(p.price_from) : "ver"}</span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {pending && <p className="animate-pulse text-xs text-muted">pensando…</p>}
            {error && <p className="text-xs text-primary">{error}</p>}
            <div ref={end} />
          </div>
          {suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2 px-4 pb-2">
              {suggestions.map((s) => (
                <button key={s} onClick={() => send(s)} className="rounded-full border border-border px-3 py-1 text-xs hover:border-secondary">
                  {s}
                </button>
              ))}
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex gap-2 border-t border-border p-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              maxLength={600}
              placeholder="Escreva aqui…"
              className="flex-1 rounded-xl border border-border bg-bg px-3 py-2 text-sm outline-none focus:border-secondary"
            />
            <button disabled={pending || !input.trim()} className="rounded-xl bg-primary px-4 text-sm font-medium text-white disabled:opacity-50">
              Enviar
            </button>
          </form>
        </section>
      )}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full bg-primary px-5 py-3 font-medium text-white shadow-lg transition hover:opacity-90"
        aria-expanded={open}
      >
        {open ? "Fechar" : "💬 Ajuda para escolher"}
      </button>
    </div>
  );
}
