import { describe, expect, it } from "vitest";
import { formToPayload, formatMoney, formatPercent } from "../src/lib/form";
import { findResource, RESOURCES } from "../src/lib/resources";
import { signSession, verifySession, SESSION_TTL_SECONDS } from "../src/lib/session";

describe("sessão", () => {
  const secret = "segredo-de-teste";

  it("assina e verifica", async () => {
    const token = await signSession(secret, 1000);
    expect(await verifySession(secret, token, 1001)).toBe(true);
  });

  it("expira", async () => {
    const token = await signSession(secret, 1000);
    expect(await verifySession(secret, token, 1000 + SESSION_TTL_SECONDS + 1)).toBe(false);
  });

  it("rejeita segredo errado, adulteração e lixo", async () => {
    const token = await signSession(secret, 1000);
    expect(await verifySession("outro", token, 1001)).toBe(false);
    const [exp, sig] = token.split(".");
    expect(await verifySession(secret, `${Number(exp) + 9999}.${sig}`, 1001)).toBe(false);
    expect(await verifySession(secret, "lixo", 1001)).toBe(false);
    expect(await verifySession(undefined, token, 1001)).toBe(false);
  });
});

describe("formToPayload", () => {
  const materiais = findResource("materiais")!;

  function fd(entries: [string, string][]): FormData {
    const f = new FormData();
    for (const [k, v] of entries) f.append(k, v);
    return f;
  }

  it("converte tipos para a API (dinheiro como string)", () => {
    const payload = formToPayload(
      materiais.fields,
      fd([
        ["kind", "PLA"],
        ["color_name", "Branco"],
        ["color_hex", "#FFFFFF"],
        ["price_per_kg", "99,90"],
        ["stock_grams", "1000"],
        ["active", "on"],
      ]),
      "create",
    );
    expect(payload).toMatchObject({ price_per_kg: "99.90", stock_grams: 1000, active: true });
    expect(payload).not.toHaveProperty("brand"); // opcional vazio omitido na criação
  });

  it("na edição limpa opcionais e ignora campos só de criação", () => {
    const tarifas = findResource("tarifas")!;
    const payload = formToPayload(
      tarifas.fields,
      fd([["channel", "x"], ["commission_rate", "0.12"]]),
      "update",
    );
    expect(payload).not.toHaveProperty("channel");
    expect(payload.max_price).toBeNull();
  });

  it("listas e caixas múltiplas", () => {
    const f = fd([["covered_terms", " Bluey, Bingo ,"]]);
    f.append("supported_materials", "PLA");
    f.append("supported_materials", "PETG");
    expect(formToPayload(findResource("licencas")!.fields, f, "create").covered_terms).toEqual(["Bluey", "Bingo"]);
    expect(formToPayload(findResource("impressoras")!.fields, f, "create").supported_materials).toEqual(["PLA", "PETG"]);
  });
});

describe("cadastros", () => {
  it("slugs únicos e colunas existentes nos campos (exceto calculadas)", () => {
    expect(new Set(RESOURCES.map((r) => r.slug)).size).toBe(RESOURCES.length);
    for (const r of RESOURCES) {
      const names = new Set(r.fields.map((f) => f.name));
      for (const c of r.columns) {
        if (c.cell !== "lowStock") expect(names.has(c.name), `${r.slug}.${c.name}`).toBe(true);
      }
    }
  });

  it("formata dinheiro e percentual", () => {
    expect(formatMoney("12.5")).toMatch(/12,50/);
    expect(formatPercent("0.12")).toBe("12%");
    expect(formatMoney(null)).toBe("—");
  });
});
