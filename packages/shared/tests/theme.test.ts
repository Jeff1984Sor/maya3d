import { describe, expect, it } from "vitest";
import { brandFonts, brandThemeCss } from "../src/theme";

describe("brandFonts", () => {
  it("carrega as famílias do painel e troca as variáveis de fonte", () => {
    const f = brandFonts({ heading: "Fredoka", body: "Nunito Sans", logo_texto: "nome-destaque" });
    expect(f.hrefs).toEqual([
      "https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600;700&display=swap",
      "https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;600;700&display=swap",
    ]);
    expect(f.css).toBe('html:root{--f-heading:"Fredoka";--f-body:"Nunito Sans";}');
    expect(f.logoText).toBe("nome-destaque");
  });

  it("ignora nome de fonte com CSS/URL e modo de logo desconhecido", () => {
    const f = brandFonts({ heading: 'x";}body{display:none', body: "a&b=c", logo_texto: "<script>" });
    expect(f).toEqual({ hrefs: [], css: "", logoText: "" });
  });

  it("mesma família no título e no texto carrega uma vez só", () => {
    expect(brandFonts({ heading: "Nunito", body: "Nunito" }).hrefs).toHaveLength(1);
  });
});

describe("brandThemeCss", () => {
  it("aceita as cores novas da marca (destaque, faixa, escura)", () => {
    const css = brandThemeCss({ light: { accent: "#E2604C", soft: "#F9D9D1", deep: "#3B1F2B" }, dark: {} });
    expect(css).toBe(":root{--accent:#E2604C;--soft:#F9D9D1;--deep:#3B1F2B;}");
  });
});
