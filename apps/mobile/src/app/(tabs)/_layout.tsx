import { Tabs } from "expo-router";
import { Text } from "react-native";
import { useCart } from "@/lib/cart";
import { useTheme } from "@/lib/theme";

const icon = (emoji: string) =>
  function TabIcon({ focused }: { focused: boolean }) {
    return <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.55 }}>{emoji}</Text>;
  };

export default function TabsLayout() {
  const { colors, brand } = useTheme();
  const { count } = useCart();
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.ink,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.muted,
      }}
    >
      <Tabs.Screen name="index" options={{ title: brand.name, tabBarLabel: "Início", tabBarIcon: icon("🏠") }} />
      <Tabs.Screen name="buscar" options={{ title: "Buscar", tabBarIcon: icon("🔎") }} />
      <Tabs.Screen
        name="carrinho"
        options={{ title: "Carrinho", tabBarIcon: icon("🛒"), tabBarBadge: count > 0 ? count : undefined }}
      />
      <Tabs.Screen name="pedidos" options={{ title: "Meus pedidos", tabBarLabel: "Pedidos", tabBarIcon: icon("📦") }} />
    </Tabs>
  );
}
