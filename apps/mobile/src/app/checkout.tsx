import type { CheckoutResult, ShippingQuote } from "@print3d/shared";
import * as Haptics from "expo-haptics";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, Switch, View } from "react-native";
import { Button, Card, Field, Notice, Screen, Text } from "@/components/ui";
import { errorText, store } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { formatCep, money, onlyDigits } from "@/lib/format";
import { rememberOrder } from "@/lib/orders";
import { useTheme } from "@/lib/theme";

/** Checkout com Pix (manual até o gateway). Frete recalculado pela API ao fechar o pedido. */
export default function CheckoutScreen() {
  const { colors } = useTheme();
  const { cart, token, clearLocal } = useCart();
  const [f, setF] = useState({ name: "", email: "", whatsapp: "", cep: "", street: "", number: "", complement: "", district: "" });
  const [optIn, setOptIn] = useState(true);
  const [terms, setTerms] = useState(false);
  const [quote, setQuote] = useState<ShippingQuote | null>(null);
  const [option, setOption] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF((cur) => ({ ...cur, [k]: v }));

  async function calcShipping() {
    setBusy(true);
    try {
      const q = await store<ShippingQuote>("/shipping", {
        body: { cep: onlyDigits(f.cep), subtotal: cart?.subtotal ?? "0", cart_token: token },
      });
      setQuote(q);
      setOption(q.options[0]?.id ?? null);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function placeOrder() {
    if (!token || !option) return;
    setBusy(true);
    try {
      const out = await store<CheckoutResult>("/checkout", {
        body: {
          cart_token: token,
          name: f.name.trim(),
          email: f.email.trim(),
          whatsapp: f.whatsapp.trim(),
          whatsapp_opt_in: optIn,
          accept_terms: terms,
          cep: onlyDigits(f.cep),
          street: f.street.trim(),
          number: f.number.trim(),
          complement: f.complement.trim() || null,
          district: f.district.trim() || null,
          shipping_option: option,
        },
      });
      await rememberOrder({ token: out.public_token, number: out.order_number, at: new Date().toISOString() });
      await clearLocal();
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      router.replace({ pathname: "/pedido/[token]", params: { token: out.public_token } });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const chosen = quote?.options.find((o) => o.id === option);
  const shipping = chosen?.price ? Number(chosen.price) : 0;

  return (
    <Screen>
      {error && <Notice text={error} />}
      <Card>
        <Text variant="heading">Seus dados</Text>
        <Field label="Nome" value={f.name} onChangeText={set("name")} autoComplete="name" />
        <Field label="E-mail" value={f.email} onChangeText={set("email")} keyboardType="email-address" autoCapitalize="none" autoComplete="email" />
        <Field label="WhatsApp" value={f.whatsapp} onChangeText={set("whatsapp")} keyboardType="phone-pad" placeholder="+55 15 99999-0000" />
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <Switch value={optIn} onValueChange={setOptIn} />
          <Text variant="small">Receber avisos do pedido pelo WhatsApp</Text>
        </View>
      </Card>

      <Card>
        <Text variant="heading">Entrega</Text>
        <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-end" }}>
          <View style={{ flex: 1 }}>
            <Field label="CEP" value={f.cep} onChangeText={(v) => set("cep")(formatCep(v))} keyboardType="number-pad" maxLength={9} />
          </View>
          <Button kind="secondary" title="Ver opções" onPress={() => void calcShipping()} disabled={onlyDigits(f.cep).length !== 8} />
        </View>
        {quote && (
          <>
            <Text variant="small">
              {quote.city}/{quote.uf}
            </Text>
            {quote.options.map((o) => (
              <Pressable
                key={o.id}
                onPress={() => setOption(o.id)}
                style={{
                  borderWidth: 1,
                  borderRadius: 12,
                  padding: 12,
                  borderColor: o.id === option ? colors.secondary : colors.border,
                }}
              >
                <Text style={{ fontWeight: "700" }}>
                  {o.label} · {o.price === null ? "a combinar" : money(o.price)}
                </Text>
                {o.detail ? <Text variant="small">{o.detail}</Text> : null}
              </Pressable>
            ))}
            {quote.missing_for_free && <Text variant="small">Faltam {money(quote.missing_for_free)} para o frete grátis.</Text>}
            <Field label="Rua" value={f.street} onChangeText={set("street")} />
            <Field label="Número" value={f.number} onChangeText={set("number")} />
            <Field label="Complemento" value={f.complement} onChangeText={set("complement")} />
            <Field label="Bairro" value={f.district} onChangeText={set("district")} />
          </>
        )}
      </Card>

      <Card>
        <Text variant="muted">Total</Text>
        <Text variant="price">{money(Number(cart?.subtotal ?? 0) + shipping)}</Text>
        <Text variant="small">Pagamento por Pix: a chave aparece na próxima tela. A produção começa quando o Pix é confirmado.</Text>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <Switch value={terms} onValueChange={setTerms} />
          <Text variant="small" style={{ flex: 1 }}>
            Li e aceito os termos e a política de privacidade
          </Text>
        </View>
      </Card>
      <Button
        title="Fazer pedido"
        loading={busy}
        disabled={!terms || !option || !f.name || !f.email || !f.whatsapp || !f.street || !f.number}
        onPress={() => void placeOrder()}
      />
    </Screen>
  );
}
