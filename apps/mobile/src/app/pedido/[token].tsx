import type { PublicOrder } from "@print3d/shared";
import * as Clipboard from "expo-clipboard";
import * as Haptics from "expo-haptics";
import { Stack, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { View } from "react-native";
import { Button, Card, Loading, Notice, Screen, Text } from "@/components/ui";
import { errorText, store } from "@/lib/api";
import { money } from "@/lib/format";
import { useTheme } from "@/lib/theme";

export default function OrderScreen() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { colors } = useTheme();
  const [order, setOrder] = useState<PublicOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setOrder(await store<PublicOrder>(`/orders/${encodeURIComponent(token)}`));
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error && !order) return <Screen><Notice text={error} /></Screen>;
  if (!order) return <Loading />;

  return (
    <Screen refreshing={loading} onRefresh={() => void load()}>
      <Stack.Screen options={{ title: `Pedido #${order.number}` }} />
      <Card>
        <Text variant="heading">{order.status_label}</Text>
        <Text variant="muted">{order.progress}</Text>
        <Text variant="price">{money(order.total)}</Text>
      </Card>

      {order.pix && (
        <Card>
          <Text variant="heading">Pague com Pix</Text>
          <Text variant="muted">Valor: {money(order.pix.amount)}</Text>
          {order.pix.name && <Text variant="small">Recebedor: {order.pix.name}</Text>}
          {order.pix.key ? (
            <>
              <Text selectable style={{ fontWeight: "700" }}>
                {order.pix.key}
              </Text>
              <Button
                title={copied ? "Chave copiada ✓" : "Copiar chave Pix"}
                onPress={async () => {
                  await Clipboard.setStringAsync(order.pix?.key ?? "");
                  void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
                  setCopied(true);
                }}
              />
            </>
          ) : (
            <Text variant="small">A loja vai enviar a chave pelo WhatsApp.</Text>
          )}
          <Text variant="small">Assim que o pagamento for confirmado, seu pedido entra em produção.</Text>
        </Card>
      )}

      <Card>
        <Text variant="heading">Itens</Text>
        {order.items.map((it, i) => (
          <Text key={i}>
            {it.quantity}× {it.title}
            {Object.values(it.personalization).length ? ` — ${Object.values(it.personalization).join(", ")}` : ""}
          </Text>
        ))}
        <Text variant="small">Frete: {money(order.shipping)}</Text>
      </Card>

      <Card>
        <Text variant="heading">Andamento</Text>
        {order.timeline.map((t, i) => (
          <View key={i} style={{ flexDirection: "row", gap: 10 }}>
            <View style={{ width: 10, height: 10, borderRadius: 5, marginTop: 6, backgroundColor: colors.secondary }} />
            <View style={{ flex: 1 }}>
              <Text>{t.label}</Text>
              <Text variant="small">{new Date(t.at).toLocaleString("pt-BR")}</Text>
            </View>
          </View>
        ))}
      </Card>
    </Screen>
  );
}
