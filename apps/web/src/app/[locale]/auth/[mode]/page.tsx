import { notFound } from "next/navigation";

import { LoginForm } from "@/components/LoginForm";
import { RegisterForm } from "@/components/RegisterForm";
import { t, type Locale } from "@/lib/i18n";

export default async function AuthPage({
  params,
}: {
  params: Promise<{ locale: string; mode: string }>;
}) {
  const { locale, mode } = await params;
  const lang = locale as Locale;
  if (mode !== "login" && mode !== "register") notFound();

  return (
    <div className="mx-auto max-w-md space-y-6">
      <h1 className="text-2xl font-bold text-ink">
        {mode === "login" ? t(lang, "auth.login") : t(lang, "auth.register")}
      </h1>
      <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
        {mode === "login" ? <LoginForm /> : <RegisterForm />}
      </div>
    </div>
  );
}