import type { Home, Niche, PageLink, StoreSettings } from "@print3d/shared";
import { Image } from "expo-image";
import { Link, router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { FlatList, Pressable, View } from "react-native";
import { ProductCard } from "@/components/product-card";
import { Button, Card, Chip, Loading, Notice, Screen, Text } from "@/components/ui";
import { errorText, media, store } from "@/lib/api";
import { useTheme } from "@/lib/theme";

export default function HomeScreen() {
  const { brand, colors } = useTheme();
  const [home, setHome] = useState<Home | null>(null);
  const [niches, setNiches] = useState<Niche[]>([]);
  const [pages, setPages] = useState<PageLink[]>([]);
  const [settings, setSettings] = useState<StoreSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [h, n, p, s] = await Promise.all([
        store<Home>("/home"),
        store<Niche[]>("/niches"),
        store<PageLink[]>("/pages"),
        store<StoreSettings>("/settings"),
      ]);
      setHome(h);
      setNiches(n.filter((x) => x.products > 0));
      setPages(p);
      setSettings(s);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !home) return <Loading />;
  const hero = home?.hero ?? {};
  const heroImage = media(hero.image);

  return (
    <Screen refreshing={loading} onRefresh={load}>
      {error && <Notice text={error} />}
      {home?.announcement && (
        <View style={{ backgroundColor: colors.ink, borderRadius: 12, padding: 10 }}>
          <Text style={{ color: colors.bg, textAlign: "center" }} variant="small">
            {home.announcement}
          </Text>
        </View>
      )}

      <Card>
        {heroImage && <Image source={heroImage} style={{ width: "100%", aspectRatio: 4 / 3, borderRadius: 12 }} contentFit="cover" />}
        <Text variant="title">{hero.title || brand.tagline || "Peças impressas em 3D, feitas para você"}</Text>
        <Text variant="muted">{hero.subtitle || "Personalize com nome, cor e tamanho."}</Text>
        <Button title={hero.cta_label || "Ver catálogo"} onPress={() => router.push("/buscar")} />
        {settings?.assistant_enabled && (
          <Button kind="secondary" title="💬 Ajuda para escolher" onPress={() => router.push("/assistente")} />
        )}
      </Card>

      {niches.length > 0 && (
        <View style={{ gap: 8 }}>
          <Text variant="heading">Escolha por tema</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {niches.map((n) => (
              <Chip key={n.slug} label={n.name} onPress={() => router.push({ pathname: "/buscar", params: { niche: n.slug, label: n.name } })} />
            ))}
          </View>
        </View>
      )}

      {(home?.sections ?? []).map((section) => (
        <View key={section.title} style={{ gap: 8 }}>
          <Text variant="heading">{section.title}</Text>
          <FlatList
            horizontal
            data={section.products}
            keyExtractor={(p) => p.slug}
            renderItem={({ item }) => <ProductCard product={item} width={170} />}
            ItemSeparatorComponent={() => <View style={{ width: 10 }} />}
            showsHorizontalScrollIndicator={false}
          />
        </View>
      ))}

      {pages.length > 0 && (
        <View style={{ gap: 6, marginTop: 8 }}>
          {pages.map((p) => (
            <Link key={p.slug} href={{ pathname: "/pagina/[slug]", params: { slug: p.slug } }} asChild>
              <Pressable>
                <Text variant="muted">{p.title}</Text>
              </Pressable>
            </Link>
          ))}
        </View>
      )}
    </Screen>
  );
}
