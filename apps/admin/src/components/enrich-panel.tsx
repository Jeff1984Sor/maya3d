"use client";

import { useState, useTransition } from "react";
import { enrichProduct, type EnrichState } from "@/actions/ai";
import { Alert, Button, inputClass } from "./ui";

/**
 * ✨ Enriquecer com IA (spec 5.5): poucas palavras → preenche o formulário do produto.
 * Só sugere: os campos ficam destacados e o dono revisa antes de salvar.
 */
export function EnrichPanel({ formId }: { formId: string }) {
  const [hint, setHint] = useState("");
  const [state, setState] = useState<EnrichState>({});
  const [pending, start] = useTransition();

  function fill(s: NonNullable<EnrichState["suggestion"]>) {
    const form = document.getElementById(formId) as HTMLFormElement | null;
    if (!form) return;
    const faq = s.faq.map((f) => `• ${f.question}\n  ${f.answer}`).join("\n");
    const description = [s.description, "", ...s.bullets.map((b) => `• ${b}`), faq ? `\nPerguntas frequentes\n${faq}` : ""]
      .join("\n")
      .trim();
    const values: Record<string, string> = {
      title: s.title,
      category: s.category,
      subcategory: s.subcategory ?? "",
      description,
      tags: s.tags.join(", "),
      occasions: s.occasions.join(", "),
    };
    for (const [name, value] of Object.entries(values)) {
      const el = form.elements.namedItem(name) as HTMLInputElement | HTMLTextAreaElement | null;
      if (!el) continue;
      el.value = value;
      el.classList.add("ring-2", "ring-secondary/50"); // destaca o que a IA sugeriu
    }
  }

  function run() {
    const form = document.getElementById(formId) as HTMLFormElement | null;
    const niche = (form?.elements.namedItem("niche") as HTMLSelectElement | null)?.value ?? "";
    start(async () => {
      const result = await enrichProduct(hint, niche);
      setState(result);
      if (result.suggestion) fill(result.suggestion);
    });
  }

  return (
    <div className="mb-6 rounded-2xl border border-secondary/40 bg-secondary/5 p-4">
      <p className="mb-2 text-sm font-medium">✨ Enriquecer com IA</p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={hint}
          onChange={(e) => setHint(e.target.value)}
          placeholder="ex.: Nossa Senhora Aparecida 15cm manto azul"
          className={inputClass}
        />
        <Button type="button" onClick={run} disabled={pending || hint.trim().length < 3}>
          {pending ? "Pensando…" : "Preencher"}
        </Button>
      </div>
      <p className="mt-2 text-xs text-muted">
        Escolha o nicho no formulário antes. A IA não inventa medidas, gramas nem preço; revise os campos destacados.
      </p>
      {state.error && (
        <div className="mt-3">
          <Alert tone="error">{state.error}</Alert>
        </div>
      )}
      {state.suggestion && state.approved === false && (
        <div className="mt-3">
          <Alert tone="error">
            O Guardião bloquearia esta sugestão: {state.violations?.map((v) => v.message).join("; ")}. Ajuste antes de salvar.
          </Alert>
        </div>
      )}
      {state.suggestion && state.suggestion.color_ideas.length > 0 && (
        <p className="mt-2 text-xs text-muted">Sugestão de cores: {state.suggestion.color_ideas.join(", ")}</p>
      )}
    </div>
  );
}
