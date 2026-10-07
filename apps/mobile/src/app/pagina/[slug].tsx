import { Stack, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { View } from "react-native";
import { Loading, Notice, Screen, Text } from "@/components/ui";
import { errorText, store } from "@/lib/api";
import { markdownBlocks, plain } from "@/lib/format";

type Page = { slug: string; title: string; body: string };

/** Páginas institucionais (sobre, trocas, privacidade) editadas no painel. */
export default function InstitutionalScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    store<Page>(`/pages/${encodeURIComponent(slug)}`)
      .then(setPage)
      .catch((e) => setError(errorText(e)));
  }, [slug]);

  if (error) return <Screen><Notice text={error} /></Screen>;
  if (!page) return <Loading />;
  return (
    <Screen>
      <Stack.Screen options={{ title: page.title }} />
      {markdownBlocks(page.body).map((b, i) =>
        b.kind === "h" ? (
          <Text key={i} variant="heading">
            {plain(b.lines[0] ?? "")}
          </Text>
        ) : b.kind === "p" ? (
          <Text key={i}>{plain(b.lines[0] ?? "")}</Text>
        ) : (
          <View key={i} style={{ gap: 4 }}>
            {b.lines.map((l, j) => (
              <Text key={j}>
                {b.kind === "ol" ? `${j + 1}. ` : "• "}
                {plain(l)}
              </Text>
            ))}
          </View>
        ),
      )}
    </Screen>
  );
}
