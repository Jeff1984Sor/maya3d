import * as Haptics from "expo-haptics";
import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text as RNText,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type TextStyle,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTheme } from "@/lib/theme";

export function Screen({
  children,
  refreshing,
  onRefresh,
  padded = true,
}: {
  children: ReactNode;
  refreshing?: boolean;
  onRefresh?: () => void;
  padded?: boolean;
}) {
  const { colors } = useTheme();
  return (
    <SafeAreaView edges={["left", "right"]} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView
        contentContainerStyle={[padded && styles.padded, { gap: 16 }]}
        keyboardShouldPersistTaps="handled"
        refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} /> : undefined}
      >
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}

type Variant = "title" | "heading" | "body" | "muted" | "small" | "price";

export function Text({
  children,
  variant = "body",
  style,
  selectable,
}: {
  children: ReactNode;
  variant?: Variant;
  style?: StyleProp<TextStyle>;
  selectable?: boolean;
}) {
  const { colors } = useTheme();
  const base: Record<Variant, TextStyle> = {
    title: { fontSize: 28, fontWeight: "800", color: colors.ink },
    heading: { fontSize: 20, fontWeight: "700", color: colors.ink },
    body: { fontSize: 16, color: colors.ink, lineHeight: 22 },
    muted: { fontSize: 15, color: colors.muted, lineHeight: 21 },
    small: { fontSize: 13, color: colors.muted },
    price: { fontSize: 24, fontWeight: "800", color: colors.primary },
  };
  return (
    <RNText selectable={selectable} style={[base[variant], style]}>
      {children}
    </RNText>
  );
}

export function Button({
  title,
  onPress,
  kind = "primary",
  disabled,
  loading,
  style,
}: {
  title: string;
  onPress: () => void;
  kind?: "primary" | "secondary";
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useTheme();
  const primary = kind === "primary";
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled || loading}
      onPress={() => {
        void Haptics.selectionAsync();
        onPress();
      }}
      style={({ pressed }) => [
        styles.button,
        {
          backgroundColor: primary ? colors.primary : colors.surface,
          borderColor: primary ? colors.primary : colors.border,
          opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
        },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={primary ? "#fff" : colors.ink} />
      ) : (
        <RNText style={{ color: primary ? "#fff" : colors.ink, fontWeight: "700", fontSize: 16 }}>{title}</RNText>
      )}
    </Pressable>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const { colors } = useTheme();
  return <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }, style]}>{children}</View>;
}

export function Field(props: TextInputProps & { label?: string }) {
  const { colors } = useTheme();
  const { label, style, ...rest } = props;
  return (
    <View style={{ gap: 6 }}>
      {label ? <Text variant="small">{label}</Text> : null}
      <TextInput
        placeholderTextColor={colors.muted}
        style={[styles.input, { borderColor: colors.border, color: colors.ink, backgroundColor: colors.surface }, style]}
        {...rest}
      />
    </View>
  );
}

export function Chip({ label, active, onPress }: { label: string; active?: boolean; onPress: () => void }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={() => {
        void Haptics.selectionAsync();
        onPress();
      }}
      style={[styles.chip, { borderColor: active ? colors.ink : colors.border, backgroundColor: active ? colors.ink : colors.surface }]}
    >
      <RNText style={{ color: active ? colors.bg : colors.ink }}>{label}</RNText>
    </Pressable>
  );
}

export function Notice({ text, tone = "error" }: { text: string; tone?: "error" | "ok" }) {
  const { colors } = useTheme();
  const color = tone === "error" ? colors.primary : colors.secondary;
  return (
    <View style={[styles.notice, { borderColor: color }]}>
      <RNText style={{ color }}>{text}</RNText>
    </View>
  );
}

export const Loading = () => {
  const { colors } = useTheme();
  return <ActivityIndicator style={{ marginTop: 40 }} color={colors.primary} />;
};

const styles = StyleSheet.create({
  padded: { padding: 16, paddingBottom: 40 },
  button: { borderRadius: 14, borderWidth: 1, paddingVertical: 14, paddingHorizontal: 18, alignItems: "center" },
  card: { borderRadius: 18, borderWidth: 1, padding: 14, gap: 8 },
  input: { borderWidth: 1, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 11, fontSize: 16 },
  chip: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 8 },
  notice: { borderWidth: 1, borderRadius: 12, padding: 12 },
});
