import type { ProductCard as Card } from "@print3d/shared";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { FlatList, View } from "react-native";
import { ProductCard } from "@/components/product-card";
import { Button, Chip, Field, Loading, Notice, Text } from "@/components/ui";
import { errorText, store } from "@/lib/api";
import { useTheme } from "@/lib/theme";

/** Busca por palavra ou por significado (a API decide); filtro por tema vindo do Início. */
export default function SearchScreen() {
  const params = useLocalSearchParams<{ niche?: string; label?: string }>();
  const { colors } = useTheme();
  const [q, setQ] = useState("");
  const [niche, setNiche] = useState<string | undefined>(params.niche);
  const [items, setItems] = useState<Card[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => setNiche(params.niche), [params.niche]);

  const search = useCallback(async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams({ limit: "40" });
      if (q.trim()) query.set("q", q.trim());
      if (niche) query.set("niche", niche);
      setItems(await store<Card[]>(`/products?${query.toString()}`));
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [q, niche]);

  useEffect(() => {
    void search();
    // busca de novo quando muda o tema; o texto busca no "enviar"
  }, [niche]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: 16, gap: 12 }}>
      <Field
        placeholder="ex.: presente para madrinha, chaveiro com nome…"
        value={q}
        onChangeText={setQ}
        returnKeyType="search"
        onSubmitEditing={() => void search()}
      />
      <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
        {niche && <Chip label={`✕ ${params.label ?? niche}`} active onPress={() => setNiche(undefined)} />}
        <Chip label="💬 Ajuda para escolher" onPress={() => router.push("/assistente")} />
      </View>
      {error && <Notice text={error} />}
      {loading && !items ? (
        <Loading />
      ) : (
        <FlatList
          data={items ?? []}
          numColumns={2}
          keyExtractor={(p) => p.slug}
          columnWrapperStyle={{ gap: 10 }}
          contentContainerStyle={{ gap: 10, paddingBottom: 40 }}
          refreshing={loading}
          onRefresh={() => void search()}
          renderItem={({ item }) => (
            <View style={{ flex: 1 }}>
              <ProductCard product={item} />
            </View>
          )}
          ListEmptyComponent={
            <View style={{ gap: 12, paddingTop: 24 }}>
              <Text variant="muted">Nada encontrado. Tente outras palavras ou peça ajuda.</Text>
              <Button kind="secondary" title="💬 Ajuda para escolher" onPress={() => router.push("/assistente")} />
            </View>
          }
        />
      )}
    </View>
  );
}
