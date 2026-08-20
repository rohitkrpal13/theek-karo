import type { Metadata } from "next";

import { SubmitWizard } from "@/components/SubmitWizard";

export const metadata: Metadata = { title: "Submit a report — Theek Karo" };

export default async function SubmitPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const { category } = await searchParams;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
        <SubmitWizard initialCategory={category} />
      </div>
    </div>
  );
}