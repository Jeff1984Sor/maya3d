import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Pressable } from "react-native";
import { Button, Card, Screen, Text } from "@/components/ui";
import { savedOrders, type SavedOrder } from "@/lib/orders";

/** Pedidos feitos neste aparelho (sem login, até existir conta com domínio). */
export default function OrdersScreen() {
  const [orders, setOrders] = useState<SavedOrder[]>([]);

  useFocusEffect(
    useCallback(() => {
      void savedOrders().then(setOrders);
    }, []),
  );

  if (orders.length === 0) {
    return (
      <Screen>
        <Text variant="heading">Nenhum pedido neste aparelho ainda</Text>
        <Text variant="muted">Os pedidos que você fizer pelo app aparecem aqui, com o andamento da produção.</Text>
        <Button title="Ver catálogo" onPress={() => router.push("/buscar")} />
      </Screen>
    );
  }
  return (
    <Screen>
      {orders.map((o) => (
        <Pressable key={o.token} onPress={() => router.push({ pathname: "/pedido/[token]", params: { token: o.token } })}>
          <Card>
            <Text variant="heading">Pedido #{o.number}</Text>
            <Text variant="small">{new Date(o.at).toLocaleDateString("pt-BR")} · toque para ver o andamento</Text>
          </Card>
        </Pressable>
      ))}
    </Screen>
  );
}
