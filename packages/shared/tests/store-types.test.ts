import { describe, expect, it } from "vitest";
import { apiMediaUrl, storeErrorMessage } from "../src/store-types";
import { brandPalette, DEFAULT_TOKENS } from "../src/theme";

describe("contratos da loja", () => {
  it("imagem /m/ vira endereço da API (app fala direto com ela)", () => {
    expect(apiMediaUrl("http://api:8000/", "/m/media/produtos/1/a-480.webp")).toBe("http://api:8000/v1/store/media/media/produtos/1/a-480.webp");
    expect(apiMediaUrl("http://api", "https://cdn/x.webp")).toBe("https://cdn/x.webp");
    expect(apiMediaUrl("http://api", "/outra/coisa")).toBeNull();
    expect(apiMediaUrl("http://api", null)).toBeNull();
  });

  it("erro do FastAPI vira frase", () => {
    expect(storeErrorMessage("sem estoque", "x")).toBe("sem estoque");
    expect(storeErrorMessage([{ msg: "a" }, { msg: "b" }], "x")).toBe("a · b");
    expect(storeErrorMessage(undefined, "falhou")).toBe("falhou");
  });

  it("paleta da marca só aceita hex válido", () => {
    const p = brandPalette({ light: { primary: "#112233", ink: "red;}" }, dark: {} }, "light");
    expect(p.primary).toBe("#112233");
    expect(p.ink).toBe(DEFAULT_TOKENS.light.ink);
  });
});
