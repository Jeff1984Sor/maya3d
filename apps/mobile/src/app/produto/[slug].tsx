import type { Product } from "@print3d/shared";
import * as Haptics from "expo-haptics";
import { Image } from "expo-image";
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { FlatList, Pressable, useWindowDimensions, View } from "react-native";
import { Button, Chip, Field, Loading, Notice, Screen, Text } from "@/components/ui";
import { errorText, media, store } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { money } from "@/lib/format";
import { useTheme } from "@/lib/theme";

export default function ProductScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const { colors } = useTheme();
  const { width } = useWindowDimensions();
  const { add } = useCart();
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [variantId, setVariantId] = useState<number | null>(null);
  const [colorId, setColorId] = useState<number | null>(null);
  const [qty, setQty] = useState(1);
  const [text, setText] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    store<Product>(`/products/${encodeURIComponent(slug)}`)
      .then((p) => {
        setProduct(p);
        const first = p.variants.find((v) => v.price_pix) ?? p.variants[0];
        setVariantId(first?.id ?? null);
        setColorId(first?.colors[0]?.material_id ?? null);
      })
      .catch((e) => setError(errorText(e)));
  }, [slug]);

  if (error) return <Screen><Notice text={error} /></Screen>;
  if (!product) return <Loading />;
  const variant = product.variants.find((v) => v.id === variantId) ?? product.variants[0];
  const images = product.images ?? [];

  async function addToCart() {
    if (!variant) return;
    setAdding(true);
    try {
      await add({
        variant_id: variant.id,
        quantity: qty,
        material_id: colorId,
        personalization: text.trim() ? { texto: text.trim() } : {},
      });
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      router.push("/carrinho");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setAdding(false);
    }
  }

  return (
    <Screen padded={false}>
      <Stack.Screen options={{ title: product.title }} />
      {images.length > 0 ? (
        <FlatList
          horizontal
          pagingEnabled
          data={images}
          keyExtractor={(i) => i.url}
          renderItem={({ item }) => (
            <Image source={media(item.url)} style={{ width, height: width, backgroundColor: "#fff" }} contentFit="contain" />
          )}
          showsHorizontalScrollIndicator={false}
        />
      ) : (
        <View style={{ height: width * 0.8, alignItems: "center", justifyContent: "center", backgroundColor: "#fff" }}>
          <Text style={{ fontSize: 90 }}>✨</Text>
        </View>
      )}

      <View style={{ padding: 16, gap: 16 }}>
        <Text variant="title">{product.title}</Text>
        {variant?.price_pix ? (
          <View>
            <Text variant="price">{money(Number(variant.price_pix) * qty)}</Text>
            <Text variant="small">no Pix · {money(Number(variant.price_card ?? variant.price_pix) * qty)} no cartão</Text>
          </View>
        ) : (
          <Notice text="Produto sem preço no momento. Fale com a loja pelo WhatsApp para um orçamento." />
        )}

        {product.variants.length > 1 && (
          <View style={{ gap: 8 }}>
            <Text variant="small">Opção</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              {product.variants.map((v) => (
                <Chip
                  key={v.id}
                  label={v.label}
                  active={v.id === variant?.id}
                  onPress={() => {
                    setVariantId(v.id);
                    setColorId(v.colors[0]?.material_id ?? null);
                  }}
                />
              ))}
            </View>
          </View>
        )}

        {variant && variant.colors.length > 0 && (
          <View style={{ gap: 8 }}>
            <Text variant="small">Cor: {variant.colors.find((c) => c.material_id === colorId)?.name ?? ""}</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
              {variant.colors.map((c) => (
                <Pressable
                  key={c.material_id}
                  accessibilityLabel={c.name}
                  onPress={() => {
                    void Haptics.selectionAsync();
                    setColorId(c.material_id);
                  }}
                  style={{
                    width: 38,
                    height: 38,
                    borderRadius: 19,
                    backgroundColor: c.hex,
                    borderWidth: c.material_id === colorId ? 3 : 1,
                    borderColor: c.material_id === colorId ? colors.primary : colors.border,
                  }}
                />
              ))}
            </View>
          </View>
        )}

        {product.customizable && (
          <Field label="Personalização (nome, frase…)" value={text} onChangeText={setText} maxLength={60} />
        )}

        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          <Chip label="−" onPress={() => setQty(Math.max(1, qty - 1))} />
          <Text variant="heading">{qty}</Text>
          <Chip label="+" onPress={() => setQty(Math.min(999, qty + 1))} />
          <Button style={{ flex: 1 }} title="Adicionar ao carrinho" onPress={() => void addToCart()} loading={adding} disabled={!variant?.price_pix} />
        </View>
        {qty > 10 && <Text variant="small">Pedidos acima de 10 unidades passam por aprovação de amostra antes da produção.</Text>}

        {product.description && <Text variant="muted">{product.description}</Text>}
        {(product.disclaimers.length > 0 || product.attribution) && (
          <View style={{ gap: 4 }}>
            {product.disclaimers.map((d) => (
              <Text key={d} variant="small">
                • {d}
              </Text>
            ))}
            {product.attribution && <Text variant="small">{product.attribution}</Text>}
          </View>
        )}
      </View>
    </Screen>
  );
}
