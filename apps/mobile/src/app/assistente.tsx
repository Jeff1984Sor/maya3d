import type { AssistantAnswer, AssistantTurn, ProductCard as Card } from "@print3d/shared";
import { useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, View } from "react-native";
import { ProductCard } from "@/components/product-card";
import { Button, Chip, Field, Notice, Text } from "@/components/ui";
import { errorText, store } from "@/lib/api";
import { useTheme } from "@/lib/theme";

type Message = AssistantTurn & { products?: Card[] };
const STARTERS = ["Presente para madrinha de batismo", "Lembrancinha para aniversário", "Algo personalizado com nome"];

/** Assistente de compra: só indica peças do catálogo (a API garante). */
export default function AssistantScreen() {
  const { colors } = useTheme();
  const [messages, setMessages] = useState<Message[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>(STARTERS);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scroll = useRef<ScrollView>(null);

  async function send(text: string) {
    const content = text.trim().slice(0, 600);
    if (!content || busy) return;
    const history: Message[] = [...messages, { role: "user", content }];
    setMessages(history);
    setInput("");
    setSuggestions([]);
    setBusy(true);
    try {
      const res = await store<AssistantAnswer>("/assistant", {
        body: { messages: history.slice(-12).map(({ role, content: c }) => ({ role, content: c })) },
        timeoutMs: 45000,
      });
      setMessages((m) => [...m, { role: "assistant", content: res.reply, products: res.products }]);
      setSuggestions(res.suggestions);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
      setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 100);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: colors.bg }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView ref={scroll} contentContainerStyle={{ padding: 16, gap: 12 }}>
        <Text variant="muted">Oi! Me conta para quem é ou qual a ocasião, que eu te mostro peças que combinam. 😊</Text>
        {messages.map((m, i) => (
          <View key={i} style={{ alignItems: m.role === "user" ? "flex-end" : "flex-start", gap: 8 }}>
            <View
              style={{
                maxWidth: "88%",
                borderRadius: 16,
                padding: 12,
                backgroundColor: m.role === "user" ? colors.primary : colors.surface,
              }}
            >
              <Text style={{ color: m.role === "user" ? "#fff" : colors.ink }}>{m.content}</Text>
            </View>
            {m.products?.map((p) => (
              <View key={p.slug} style={{ width: 200 }}>
                <ProductCard product={p} />
              </View>
            ))}
          </View>
        ))}
        {busy && <Text variant="small">pensando…</Text>}
        {error && <Notice text={error} />}
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {suggestions.map((s) => (
            <Chip key={s} label={s} onPress={() => void send(s)} />
          ))}
        </View>
      </ScrollView>
      <View style={{ flexDirection: "row", gap: 8, padding: 12, borderTopWidth: 1, borderColor: colors.border }}>
        <View style={{ flex: 1 }}>
          <Field value={input} onChangeText={setInput} placeholder="Escreva aqui…" maxLength={600} onSubmitEditing={() => void send(input)} />
        </View>
        <Button title="Enviar" onPress={() => void send(input)} disabled={!input.trim() || busy} />
      </View>
    </KeyboardAvoidingView>
  );
}
