import AsyncStorage from "@react-native-async-storage/async-storage";
import type { Cart, CartLine } from "@print3d/shared";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, store } from "./api";

const KEY = "p3d:cart";

export type NewLine = {
  variant_id: number;
  quantity: number;
  material_id: number | null;
  personalization: Record<string, string>;
};

type CartState = {
  cart: Cart | null;
  count: number;
  add: (line: NewLine) => Promise<void>;
  setQuantity: (index: number, quantity: number) => Promise<void>;
  refresh: () => Promise<void>;
  clearLocal: () => Promise<void>;
  token: string | null;
};

const CartContext = createContext<CartState | null>(null);

const toLines = (cart: Cart): NewLine[] =>
  cart.items.map((i: CartLine) => ({
    variant_id: i.variant_id,
    quantity: i.quantity,
    material_id: i.material_id,
    personalization: i.personalization,
  }));

/** Carrinho guardado na API (mesmo do site); o aparelho só lembra o token. */
export function CartProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [cart, setCart] = useState<Cart | null>(null);

  const ensureToken = useCallback(async (): Promise<string> => {
    if (token) return token;
    const saved = await AsyncStorage.getItem(KEY);
    if (saved) {
      setToken(saved);
      return saved;
    }
    const created = await store<{ token: string }>("/cart", { method: "POST" });
    await AsyncStorage.setItem(KEY, created.token);
    setToken(created.token);
    return created.token;
  }, [token]);

  const refresh = useCallback(async () => {
    const saved = token ?? (await AsyncStorage.getItem(KEY));
    if (!saved) return;
    try {
      setCart(await store<Cart>(`/cart/${saved}`));
      setToken(saved);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        await AsyncStorage.removeItem(KEY); // carrinho expirado: começa outro
        setToken(null);
        setCart(null);
      } // sem internet: mantém o carrinho guardado
    }
  }, [token]);

  useEffect(() => {
    void refresh(); // só na abertura do app
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const save = useCallback(
    async (lines: NewLine[]) => {
      const t = await ensureToken();
      setCart(await store<Cart>(`/cart/${t}`, { method: "PUT", body: { items: lines } }));
    },
    [ensureToken],
  );

  const add = useCallback(
    async (line: NewLine) => {
      const t = await ensureToken();
      const current = await store<Cart>(`/cart/${t}`);
      await save([...toLines(current), line]);
    },
    [ensureToken, save],
  );

  const setQuantity = useCallback(
    async (index: number, quantity: number) => {
      if (!cart) return;
      const lines = toLines(cart);
      if (quantity <= 0) lines.splice(index, 1);
      else if (lines[index]) lines[index] = { ...lines[index], quantity };
      await save(lines);
    },
    [cart, save],
  );

  const clearLocal = useCallback(async () => {
    await AsyncStorage.removeItem(KEY);
    setToken(null);
    setCart(null);
  }, []);

  const count = cart?.items.reduce((n, i) => n + i.quantity, 0) ?? 0;
  return (
    <CartContext.Provider value={{ cart, count, add, setQuantity, refresh, clearLocal, token }}>{children}</CartContext.Provider>
  );
}

export function useCart(): CartState {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart fora do CartProvider");
  return ctx;
}
