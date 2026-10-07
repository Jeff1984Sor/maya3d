import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { View } from "react-native";
import { Button, Card, Chip, Notice, Screen, Text } from "@/components/ui";
import { errorText } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { money } from "@/lib/format";

export default function CartScreen() {
  const { cart, refresh, setQuantity } = useCart();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      void refresh();
    }, [refresh]),
  );

  async function change(index: number, quantity: number) {
    setBusy(true);
    try {
      await setQuantity(index, quantity);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (!cart || cart.items.length === 0) {
    return (
      <Screen>
        <Text variant="heading">Seu carrinho está vazio</Text>
        <Button title="Ver catálogo" onPress={() => router.push("/buscar")} />
      </Screen>
    );
  }

  return (
    <Screen refreshing={busy} onRefresh={() => void refresh()}>
      {error && <Notice text={error} />}
      {cart.items.map((line, i) => (
        <Card key={`${line.variant_id}-${i}`}>
          <Text style={{ fontWeight: "700" }}>{line.title}</Text>
          {line.color && <Text variant="small">Cor: {line.color.name}</Text>}
          {Object.entries(line.personalization).map(([k, v]) => (
            <Text key={k} variant="small">
              {k}: {v}
            </Text>
          ))}
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <Chip label="−" onPress={() => void change(i, line.quantity - 1)} />
            <Text variant="heading">{line.quantity}</Text>
            <Chip label="+" onPress={() => void change(i, line.quantity + 1)} />
            <Text style={{ marginLeft: "auto", fontWeight: "800" }}>{money(line.line_total)}</Text>
          </View>
          <Chip label="remover" onPress={() => void change(i, 0)} />
        </Card>
      ))}
      {cart.problems.map((p) => (
        <Notice key={p} text={p} />
      ))}
      <Card>
        <Text variant="muted">Subtotal</Text>
        <Text variant="price">{money(cart.subtotal)}</Text>
        <Text variant="small">Frete calculado no próximo passo, pelo CEP.</Text>
      </Card>
      <Button title="Finalizar pedido" disabled={!cart.purchasable || busy} onPress={() => router.push("/checkout")} />
    </Screen>
  );
}
