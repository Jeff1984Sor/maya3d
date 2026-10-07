/** Formatação sem dependência de React Native (testável com vitest). */

export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `R$ ${n.toFixed(2).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
}

export function onlyDigits(value: string): string {
  return value.replace(/\D/g, "");
}

export function formatCep(value: string): string {
  const d = onlyDigits(value).slice(0, 8);
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d;
}

/** Blocos do Markdown simples das páginas institucionais (mesmas regras da loja web). */
export type Block = { kind: "h" | "p" | "ul" | "ol"; lines: string[] };

export function markdownBlocks(source: string): Block[] {
  return source
    .replace(/\r\n/g, "\n")
    .split(/\n{2,}/)
    .map((block) => block.split("\n").filter((l) => l.trim()))
    .filter((lines) => lines.length > 0)
    .map((lines): Block => {
      const first = lines[0] ?? "";
      if (/^#{1,3}\s/.test(first)) return { kind: "h", lines: [first.replace(/^#+\s/, "")] };
      if (lines.every((l) => /^\s*[-*]\s/.test(l))) return { kind: "ul", lines: lines.map((l) => l.replace(/^\s*[-*]\s/, "")) };
      if (lines.every((l) => /^\s*\d+\.\s/.test(l))) return { kind: "ol", lines: lines.map((l) => l.replace(/^\s*\d+\.\s/, "")) };
      return { kind: "p", lines: [lines.join(" ")] };
    });
}

/** Tira **negrito** e *itálico* (o app mostra texto puro, sem HTML). */
export const plain = (text: string) => text.replace(/\*\*([^*]+)\*\*/g, "$1").replace(/\*([^*]+)\*/g, "$1");
