"use server";

import { createHash } from "node:crypto";
import { headers } from "next/headers";
import { StoreApiError, storeApi, type ProductCard } from "@/lib/store";

export type ChatTurn = { role: "user" | "assistant"; content: string };
export type AssistantAnswer = { reply: string; products: ProductCard[]; suggestions: string[] };

/** Visitante anônimo para o limite por minuto (hash do IP; o IP não sai daqui). */
async function clientId(): Promise<string> {
  const h = await headers();
  const ip = (h.get("x-forwarded-for") ?? h.get("x-real-ip") ?? "anon").split(",")[0]!.trim();
  return createHash("sha256").update(ip).digest("hex").slice(0, 32);
}

export async function askAssistant(messages: ChatTurn[]): Promise<AssistantAnswer | { error: string }> {
  const clean = messages
    .slice(-12)
    .map((m) => ({ role: m.role, content: String(m.content).slice(0, 600).trim() }))
    .filter((m) => m.content && (m.role === "user" || m.role === "assistant"));
  if (!clean.length || clean[clean.length - 1]!.role !== "user") return { error: "Escreva sua pergunta." };
  try {
    return await storeApi<AssistantAnswer>("/assistant", {
      method: "POST",
      body: JSON.stringify({ messages: clean, client_id: await clientId() }),
    });
  } catch (error) {
    return { error: error instanceof StoreApiError ? error.message : "O assistente não respondeu agora. Tente de novo." };
  }
}
