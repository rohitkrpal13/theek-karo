import { DepartmentAdmin } from "@/components/cases/DepartmentAdmin";
import { t, type Locale } from "@/lib/i18n";

export default async function AdminDepartmentsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const lang = locale as Locale;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold text-(--color-primary-strong)">{t(lang, "departments.title")}</h1>
      <DepartmentAdmin />
    </div>
  );
}