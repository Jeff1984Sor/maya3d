import { describe, expect, it, vi } from "vitest";
import { ApiError, FALLBACK_BRAND, brandThemeCss, createApiClient } from "../src";

describe("brandThemeCss", () => {
  it("gera variáveis para claro e escuro", () => {
    const css = brandThemeCss({ light: { primary: "#112233" }, dark: { primary: "#abc" } });
    expect(css).toBe(":root{--primary:#112233;}@media (prefers-color-scheme:dark){:root{--primary:#abc;}}");
  });

  it("descarta valores que não sejam hex (anti-injeção de CSS)", () => {
    const css = brandThemeCss({
      light: { primary: "red;} body{display:none", secondary: "#14B8A6" },
      dark: {},
    });
    expect(css).toBe(":root{--secondary:#14B8A6;}");
  });

  it("descarta chaves fora da lista", () => {
    expect(brandThemeCss({ light: { "x}y": "#fff", evil: "#000" }, dark: {} })).toBe("");
  });
});

describe("createApiClient", () => {
  const ok = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

  it("busca a marca", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok({ ...FALLBACK_BRAND, name: "Loja X" }));
    const api = createApiClient({ baseUrl: "http://api:8000/", fetch: fetchMock });
    expect((await api.getBrand()).name).toBe("Loja X");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://api:8000/v1/brand");
  });

  it("lança ApiError em 500", async () => {
    const api = createApiClient({ baseUrl: "http://a", fetch: vi.fn().mockResolvedValue(ok({}, 500)) });
    await expect(api.getBrand()).rejects.toBeInstanceOf(ApiError);
  });

  it("getBrandOrFallback nunca lança", async () => {
    const api = createApiClient({ baseUrl: "http://a", fetch: vi.fn().mockRejectedValue(new Error("down")) });
    expect(await api.getBrandOrFallback()).toEqual(FALLBACK_BRAND);
  });

  it("ready degradado (503) ainda devolve o corpo", async () => {
    const body = { status: "degraded", checks: { redis: { ok: false, detail: "X" } } };
    const api = createApiClient({ baseUrl: "http://a", fetch: vi.fn().mockResolvedValue(ok(body, 503)) });
    expect((await api.getReady()).status).toBe("degraded");
  });
});
