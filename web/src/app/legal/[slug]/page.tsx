import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LEGAL_DOCS } from "@/content/legal";
import { LegalDocument } from "@/modules/legal/components/legal-document";

type PageProps = { params: Promise<{ slug: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return LEGAL_DOCS.map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const doc = LEGAL_DOCS.find((d) => d.slug === slug);
  return doc ? { title: `${doc.title} · Compliance Navigator`, description: doc.summary } : {};
}

export default async function Page({ params }: PageProps) {
  const { slug } = await params;
  const doc = LEGAL_DOCS.find((d) => d.slug === slug);
  if (!doc) notFound();
  return <LegalDocument doc={doc} />;
}
