import { CaseList } from "@/components/cases/CaseList";
import { t, type Locale } from "@/lib/i18n";

export default async function CasesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const lang = locale as Locale;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-(--color-primary-strong)">{t(lang, "cases.title")}</h1>
        <p className="text-sm text-stone-500">{t(lang, "cases.case_no")}</p>
      </div>
      <CaseList />
    </div>
  );
}