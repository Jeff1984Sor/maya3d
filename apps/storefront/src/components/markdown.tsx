import type { ReactNode } from "react";

/**
 * Markdown mínimo das páginas institucionais: títulos (##), listas (- e 1.), negrito (**),
 * itálico (*) e parágrafos. Tudo vira texto do React (sem HTML cru): nada de script injetado.
 */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : part.startsWith("*") && part.endsWith("*") && part.length > 2 ? (
      <em key={i}>{part.slice(1, -1)}</em>
    ) : (
      part
    ),
  );
}

export function Markdown({ source }: { source: string }) {
  const blocks = source.replace(/\r\n/g, "\n").split(/\n{2,}/);
  return (
    <div className="space-y-4 leading-relaxed">
      {blocks.map((block, i) => {
        const lines = block.split("\n").filter((l) => l.trim());
        if (!lines.length) return null;
        const first = lines[0]!;
        if (/^#{1,3}\s/.test(first)) {
          const Tag = first.startsWith("###") ? "h3" : "h2";
          return (
            <Tag key={i} className={Tag === "h2" ? "font-heading text-2xl font-bold" : "font-heading text-lg font-semibold"}>
              {inline(first.replace(/^#+\s/, ""))}
            </Tag>
          );
        }
        if (lines.every((l) => /^\s*[-*]\s/.test(l))) {
          return (
            <ul key={i} className="list-disc space-y-1 pl-6">
              {lines.map((l, j) => (
                <li key={j}>{inline(l.replace(/^\s*[-*]\s/, ""))}</li>
              ))}
            </ul>
          );
        }
        if (lines.every((l) => /^\s*\d+\.\s/.test(l))) {
          return (
            <ol key={i} className="list-decimal space-y-1 pl-6">
              {lines.map((l, j) => (
                <li key={j}>{inline(l.replace(/^\s*\d+\.\s/, ""))}</li>
              ))}
            </ol>
          );
        }
        return <p key={i}>{inline(lines.join(" "))}</p>;
      })}
    </div>
  );
}
