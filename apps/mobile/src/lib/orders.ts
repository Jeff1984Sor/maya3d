import AsyncStorage from "@react-native-async-storage/async-storage";

/** "Meus pedidos" sem login: o aparelho guarda o link secreto de cada pedido feito nele. */
const KEY = "p3d:orders";

export type SavedOrder = { token: string; number: number; at: string };

export async function savedOrders(): Promise<SavedOrder[]> {
  try {
    return JSON.parse((await AsyncStorage.getItem(KEY)) ?? "[]") as SavedOrder[];
  } catch {
    return [];
  }
}

export async function rememberOrder(order: SavedOrder): Promise<void> {
  const list = (await savedOrders()).filter((o) => o.token !== order.token);
  await AsyncStorage.setItem(KEY, JSON.stringify([order, ...list].slice(0, 50)));
}
