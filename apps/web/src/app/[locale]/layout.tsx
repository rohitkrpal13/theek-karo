import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "@/components/AppShell";
import { Providers } from "@/components/Providers";
import { PwaRegistration } from "@/components/PwaRegistration";
import { LOCALES, type Locale } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "Theek Karo",
};

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params; // Next 16: async params
  if (!(LOCALES as readonly string[]).includes(locale)) notFound();

  return (
    <Providers locale={locale as Locale}>
      <div className="flex min-h-dvh flex-col">
        <AppShell>{children}</AppShell>
        <PwaRegistration />
      </div>
    </Providers>
  );
}