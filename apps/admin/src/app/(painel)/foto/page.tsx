import type { Metadata } from "next";
import { Card, PageHeader } from "@/components/ui";
import { PhotoStudio } from "./photo-studio";

export const metadata: Metadata = { title: "Foto vira peça" };

export default function FotoPage() {
  return (
    <>
      <PageHeader
        title="Foto vira peça"
        description="Litofania, placa multicor, cortador de biscoito e chaveiro de silhueta a partir de uma imagem. As fotos são apagadas automaticamente após o prazo da LGPD."
      />
      <Card>
        <PhotoStudio />
      </Card>
    </>
  );
}
