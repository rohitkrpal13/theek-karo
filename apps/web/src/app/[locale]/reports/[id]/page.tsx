import { ReportDetail } from "@/components/ReportDetail";
import { t, type Locale } from "@/lib/i18n";

export default async function ReportPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  const lang = locale as Locale;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <ReportDetail reportId={id} />
      <p className="text-xs text-stone-400">
        {t(lang, "footer.rights")} · <span lang="en">{id}</span>
      </p>
    </div>
  );
}