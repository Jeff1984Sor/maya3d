import type { ProductCard as Card } from "@print3d/shared";
import { Image } from "expo-image";
import { Link } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { media } from "@/lib/api";
import { money } from "@/lib/format";
import { useTheme } from "@/lib/theme";

const EMOJI: Record<string, string> = {
  religioso: "✝️",
  automotivo: "🚗",
  celular: "📱",
  brindes: "🎁",
  "datas-comemorativas": "🎉",
  fitness: "🏋️",
  chaveiros: "🔑",
  infantil: "🧸",
  caixas: "📦",
};

export function ProductCard({ product, width }: { product: Card; width?: number }) {
  const { colors } = useTheme();
  const image = media(product.image);
  return (
    <Link href={{ pathname: "/produto/[slug]", params: { slug: product.slug } }} asChild>
      <Pressable style={[styles.card, { width, backgroundColor: colors.surface, borderColor: colors.border }]}>
        <View style={styles.square}>
          {image ? (
            <Image source={image} style={StyleSheet.absoluteFill} contentFit="cover" transition={150} />
          ) : (
            <Text style={{ fontSize: 48 }}>{EMOJI[product.niche] ?? "✨"}</Text>
          )}
        </View>
        <View style={{ padding: 10, gap: 4 }}>
          <Text numberOfLines={2} style={{ color: colors.ink, fontWeight: "600" }}>
            {product.title}
          </Text>
          <Text style={{ color: colors.primary, fontWeight: "800", fontSize: 16 }}>
            {product.price_from ? `a partir de ${money(product.price_from)}` : "sob consulta"}
          </Text>
          {product.colors.length > 0 && (
            <View style={{ flexDirection: "row", gap: 4 }}>
              {product.colors.slice(0, 6).map((c) => (
                <View key={c} style={[styles.dot, { backgroundColor: c, borderColor: colors.border }]} />
              ))}
            </View>
          )}
        </View>
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: 18, borderWidth: 1, overflow: "hidden" },
  square: { aspectRatio: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#fff" },
  dot: { width: 12, height: 12, borderRadius: 6, borderWidth: 1 },
});
