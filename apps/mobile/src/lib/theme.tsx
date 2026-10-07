import { brandPalette, FALLBACK_BRAND, type BrandPublic } from "@print3d/shared";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useColorScheme } from "react-native";
import { API_URL } from "./api";

type Palette = ReturnType<typeof brandPalette>;
type Theme = { brand: BrandPublic; colors: Palette; dark: boolean };

const ThemeContext = createContext<Theme>({
  brand: FALLBACK_BRAND,
  colors: brandPalette(FALLBACK_BRAND.colors, "light"),
  dark: false,
});

/** Marca e cores vêm da API (painel → Marca); sem rede, o padrão neutro. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const scheme = useColorScheme();
  const dark = scheme === "dark";
  const [brand, setBrand] = useState<BrandPublic>(FALLBACK_BRAND);

  useEffect(() => {
    fetch(`${API_URL}/v1/brand`)
      .then((r) => (r.ok ? (r.json() as Promise<BrandPublic>) : null))
      .then((b) => b && setBrand(b))
      .catch(() => undefined);
  }, []);

  return (
    <ThemeContext.Provider value={{ brand, colors: brandPalette(brand.colors, dark ? "dark" : "light"), dark }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
