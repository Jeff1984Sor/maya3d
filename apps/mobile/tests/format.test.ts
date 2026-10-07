import { describe, expect, it } from "vitest";
import { formatCep, markdownBlocks, money, onlyDigits, plain } from "../src/lib/format";

describe("formatação do app", () => {
  it("dinheiro em reais", () => {
    expect(money("1234.5")).toBe("R$ 1.234,50");
    expect(money(9.9)).toBe("R$ 9,90");
    expect(money(null)).toBe("—");
    expect(money("abc")).toBe("—");
  });

  it("CEP", () => {
    expect(formatCep("18035-000")).toBe("18035-000");
    expect(formatCep("1803")).toBe("1803");
    expect(onlyDigits("+55 (15) 9")).toBe("55159");
  });

  it("markdown das páginas", () => {
    const blocks = markdownBlocks("## Trocas\n\n- um\n- dois\n\n1. a\n2. b\n\nTexto **forte**");
    expect(blocks.map((b) => b.kind)).toEqual(["h", "ul", "ol", "p"]);
    expect(blocks[1]?.lines).toEqual(["um", "dois"]);
    expect(plain("Texto **forte** e *leve*")).toBe("Texto forte e leve");
  });
});
