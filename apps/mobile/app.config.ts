import type { ExpoConfig } from "expo/config";

/**
 * Configuração do app. Nome, identificadores e endereço da API vêm do ambiente (EAS/CI),
 * nunca fixos: a marca é trocada sem mexer no código.
 *
 *   APP_NAME            nome na tela do celular (padrão neutro)
 *   APP_ID              com.empresa.loja (bundle iOS / pacote Android) — definir antes de publicar
 *   EXPO_PUBLIC_API_URL endereço público da API (https://api.<domínio> quando houver domínio)
 *   EAS_PROJECT_ID      projeto no expo.dev (eas init)
 */
const apiUrl = process.env.EXPO_PUBLIC_API_URL ?? "http://2.25.130.240:39000";
// Enquanto não há domínio com HTTPS, Android e iOS precisam liberar HTTP para a API.
const cleartext = apiUrl.startsWith("http://");
const appId = process.env.APP_ID ?? "com.print3d.loja";

const config: ExpoConfig = {
  name: process.env.APP_NAME ?? "Loja 3D",
  slug: "print3d-loja",
  scheme: "print3d",
  version: "0.1.0",
  orientation: "portrait",
  icon: "./assets/icon.png",
  userInterfaceStyle: "automatic",
  ios: {
    bundleIdentifier: appId,
    supportsTablet: true,
    infoPlist: {
      ITSAppUsesNonExemptEncryption: false,
      ...(cleartext ? { NSAppTransportSecurity: { NSAllowsArbitraryLoads: true } } : {}),
    },
  },
  android: {
    package: appId,
    adaptiveIcon: { foregroundImage: "./assets/adaptive-icon.png", backgroundColor: "#F7F4EF" },
  },
  plugins: [
    "expo-router",
    ["expo-splash-screen", { image: "./assets/splash-icon.png", imageWidth: 120, backgroundColor: "#F7F4EF" }],
    ["expo-build-properties", { android: { usesCleartextTraffic: cleartext } }],
  ],
  extra: {
    apiUrl,
    eas: process.env.EAS_PROJECT_ID ? { projectId: process.env.EAS_PROJECT_ID } : undefined,
  },
  updates: process.env.EAS_PROJECT_ID ? { url: `https://u.expo.dev/${process.env.EAS_PROJECT_ID}` } : undefined,
  runtimeVersion: { policy: "appVersion" },
};

export default config;
