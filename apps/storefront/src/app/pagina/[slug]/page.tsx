import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Markdown } from "@/components/markdown";
import { Container } from "@/components/shop";
import { StoreApiError, storeApi } from "@/lib/store";

export const revalidate = 60;
type Params = Promise<{ slug: string }>;
type Page = { slug: string; title: string; body: string };

async function load(slug: string): Promise<Page | null> {
  try {
    return await storeApi<Page>(`/pages/${encodeURIComponent(slug)}`, { revalidate: 60 });
  } catch (error) {
    if (error instanceof StoreApiError && error.status === 404) return null;
    throw error;
  }
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const page = await load((await params).slug);
  return { title: page?.title ?? "Página" };
}

export default async function InstitutionalPage({ params }: { params: Params }) {
  const page = await load((await params).slug);
  if (!page) notFound();
  return (
    <Container className="max-w-3xl py-12">
      <Markdown source={page.body} />
    </Container>
  );
}
