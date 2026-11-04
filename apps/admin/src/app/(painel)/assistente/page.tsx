import type { Metadata } from "next";
import { Card, PageHeader } from "@/components/ui";
import { AgentChat } from "./agent-chat";

export const metadata: Metadata = { title: "Assistente" };

export default function AssistentePage() {
  return (
    <>
      <PageHeader
        title="🤖 Assistente"
        description="Peça em português: buscar fotos na internet (só com licença que permite vender), transformar em peça, achar produtos, ver pedidos, mudar título ou status. O que altera algo só roda quando você confirma."
      />
      <Card>
        <AgentChat />
      </Card>
    </>
  );
}
